"""
User Profile API Adapter

프로필 업데이트 최적화 시스템과 CQRS 기반 User Profile API 간의 어댑터
내부 모델을 API 형식으로 변환하고 RabbitMQ 메시지 발행을 담당
"""

import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import asdict

import aio_pika
from aio_pika import Message, DeliveryMode
from loguru import logger

from app.core.config import settings
from app.schemas.profile_schemas import ProfileUpdateRequest, ProfileRefreshRequest
from app.services.user_profile_processor import ActivityData, ActivityType


class ProfileAPIAdapter:
    """User Profile API와의 통신을 담당하는 어댑터"""

    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None

    async def _ensure_connection(self):
        """RabbitMQ 연결 확보"""
        if not self.connection or self.connection.is_closed:
            self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.channel = await self.connection.channel()

        return self.channel

    async def send_profile_update_message(
        self,
        user_id: int,
        activity_data: ActivityData,
        update_type: str = "incremental",
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        프로필 업데이트 메시지를 RabbitMQ에 발행

        Args:
            user_id: 사용자 ID
            activity_data: 활동 데이터
            update_type: 업데이트 타입 (incremental, full)
            metadata: 추가 메타데이터

        Returns:
            발행 성공 여부
        """
        try:
            # ActivityData를 ProfileUpdateRequest 형식으로 변환
            update_request = self._convert_activity_to_update_request(
                user_id=user_id,
                activity_data=activity_data,
                update_type=update_type,
                metadata=metadata
            )

            # RabbitMQ 메시지 발행
            success = await self._publish_to_queue(
                queue_name="profile.update.queue",
                message_data=update_request.model_dump(),
                routing_key="profile.update"
            )

            if success:
                logger.info(
                    f"✅ 프로필 업데이트 메시지 발행 성공 - User ID: {user_id}, "
                    f"Activity: {activity_data.activity_type.value}"
                )
            else:
                logger.error(
                    f"❌ 프로필 업데이트 메시지 발행 실패 - User ID: {user_id}"
                )

            return success

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 프로필 업데이트 메시지 발행 중 오류: {e}")
            return False

    async def send_batch_update_message(
        self,
        user_ids: List[int],
        update_type: str = "quality_check",
        force_recalculation: bool = False
    ) -> bool:
        """
        배치 프로필 업데이트 메시지를 발행

        Args:
            user_ids: 업데이트할 사용자 ID 목록
            update_type: 업데이트 타입
            force_recalculation: 강제 재계산 여부

        Returns:
            발행 성공 여부
        """
        try:
            # 각 사용자에 대한 업데이트 메시지 생성
            success_count = 0

            for user_id in user_ids:
                update_request = ProfileUpdateRequest(
                    user_id=user_id,
                    update_type=update_type,
                    incremental_update=not force_recalculation,
                    force_recalculation=force_recalculation,
                    source_data={
                        "batch_update": True,
                        "batch_type": update_type,
                        "timestamp": datetime.now().isoformat()
                    }
                )

                if await self._publish_to_queue(
                    queue_name="profile.update.queue",
                    message_data=update_request.model_dump(),
                    routing_key="profile.batch_update"
                ):
                    success_count += 1

            logger.info(
                f"📊 배치 업데이트 메시지 발행 완료 - "
                f"성공: {success_count}/{len(user_ids)}"
            )

            return success_count == len(user_ids)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 배치 업데이트 메시지 발행 중 오류: {e}")
            return False

    async def send_profile_refresh_message(
        self,
        user_id: int,
        job_id: Optional[str] = None,
        force_full_recalculation: bool = True
    ) -> str:
        """
        프로필 재생성 메시지를 발행

        Args:
            user_id: 사용자 ID
            job_id: 작업 ID (없으면 자동 생성)
            force_full_recalculation: 전체 재계산 강제 여부

        Returns:
            작업 ID
        """
        try:
            if not job_id:
                job_id = str(uuid.uuid4())

            refresh_request = ProfileRefreshRequest(
                user_id=user_id,
                job_id=job_id,
                force_full_recalculation=force_full_recalculation,
                include_historical_data=True,
                recalculate_dependencies=["vectors", "keywords", "preferences"]
            )

            success = await self._publish_to_queue(
                queue_name="profile.refresh.queue",
                message_data=refresh_request.model_dump(),
                routing_key="profile.refresh"
            )

            if success:
                logger.info(
                    f"🔄 프로필 재생성 메시지 발행 성공 - "
                    f"User ID: {user_id}, Job ID: {job_id}"
                )
            else:
                logger.error(
                    f"❌ 프로필 재생성 메시지 발행 실패 - User ID: {user_id}"
                )
                raise RuntimeError(f"프로필 재생성 메시지 발행 실패 - User ID: {user_id}")

            return job_id

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 프로필 재생성 메시지 발행 중 오류: {e}")
            raise

    def _convert_activity_to_update_request(
        self,
        user_id: int,
        activity_data: ActivityData,
        update_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProfileUpdateRequest:
        """
        ActivityData를 ProfileUpdateRequest로 변환

        Args:
            user_id: 사용자 ID
            activity_data: 활동 데이터
            update_type: 업데이트 타입
            metadata: 추가 메타데이터

        Returns:
            변환된 ProfileUpdateRequest
        """
        # ActivityData를 딕셔너리로 변환
        source_data = asdict(activity_data)

        # 메타데이터 추가
        if metadata:
            source_data.update(metadata)

        # 관심사 추출 (ActivityData의 metadata에서)
        new_interests = []
        if 'keywords' in activity_data.metadata:
            new_interests.extend(activity_data.metadata['keywords'])
        if 'categories' in activity_data.metadata:
            new_interests.extend(activity_data.metadata['categories'])

        return ProfileUpdateRequest(
            user_id=user_id,
            update_type=update_type,
            incremental_update=True,
            new_interests=new_interests if new_interests else None,
            source_data=source_data,
            force_recalculation=False
        )

    async def _publish_to_queue(
        self,
        queue_name: str,
        message_data: Dict[str, Any],
        routing_key: str = ""
    ) -> bool:
        """
        메시지를 지정된 큐에 발행

        Args:
            queue_name: 대상 큐 이름
            message_data: 메시지 데이터
            routing_key: 라우팅 키

        Returns:
            발행 성공 여부
        """
        try:
            channel = await self._ensure_connection()

            # 큐 선언 (있는 경우 무시)
            await channel.declare_queue(
                queue_name,
                durable=True,
                arguments={"x-message-ttl": 3600000}  # 1시간 TTL
            )

            # 메시지 생성
            message_body = json.dumps(message_data, ensure_ascii=False, default=str)
            message = Message(
                message_body.encode('utf-8'),
                delivery_mode=DeliveryMode.PERSISTENT,
                headers={
                    "content_type": "application/json",
                    "routing_key": routing_key,
                    "timestamp": datetime.now().isoformat()
                }
            )

            # 메시지 발행
            await channel.default_exchange.publish(
                message,
                routing_key=queue_name
            )

            logger.debug(f"📤 메시지 발행 성공 - Queue: {queue_name}")
            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 메시지 발행 실패 - Queue: {queue_name}, 오류: {e}")
            return False

    async def close_connection(self):
        """연결 종료"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.debug("🔌 RabbitMQ 연결 종료")


class ProfileUpdateEventTranslator:
    """프로필 업데이트 이벤트를 API 형식으로 변환하는 유틸리티"""

    @staticmethod
    def bookmark_event_to_activity_data(
        bookmark_data: Dict[str, Any]
    ) -> ActivityData:
        """
        북마크 이벤트 데이터를 ActivityData로 변환

        Args:
            bookmark_data: 북마크 데이터

        Returns:
            변환된 ActivityData
        """
        # 카테고리 정규화
        categories = bookmark_data.get("category", [])
        if isinstance(categories, str):
            categories = [categories]
        elif not isinstance(categories, list):
            categories = []

        # 메타데이터 구성
        metadata = {
            "title": bookmark_data.get("title", ""),
            "description": bookmark_data.get("description", ""),
            "keywords": bookmark_data.get("keywords", []),
            "categories": categories,
            "tags": bookmark_data.get("tags", []),
            "url": bookmark_data.get("url", ""),
            "event_type": bookmark_data.get("event_type", "bookmark_created")
        }

        return ActivityData(
            activity_type=ActivityType.BOOKMARK,
            content=bookmark_data.get("content", ""),
            created_at=bookmark_data.get("event_timestamp", datetime.now()),
            metadata=metadata,
            weight=1.5  # 북마크는 높은 가중치
        )

    @staticmethod
    def chat_event_to_activity_data(
        chat_data: Dict[str, Any]
    ) -> ActivityData:
        """
        채팅 이벤트 데이터를 ActivityData로 변환

        Args:
            chat_data: 채팅 데이터

        Returns:
            변환된 ActivityData
        """
        # 채팅 메시지들에서 텍스트 추출
        messages = chat_data.get("messages", [])
        content_parts = []

        for message in messages:
            if isinstance(message, dict) and message.get("role") == "user":
                content_parts.append(message.get("content", ""))

        content = " ".join(content_parts)

        # 메타데이터 구성
        metadata = {
            "title": chat_data.get("session_title", ""),
            "description": f"채팅 세션 - {len(messages)}개 메시지",
            "keywords": chat_data.get("keywords", []),
            "categories": chat_data.get("categories", []),
            "session_duration": chat_data.get("session_duration_minutes", 0),
            "message_count": len(messages),
            "event_type": chat_data.get("event_type", "chat_completed")
        }

        return ActivityData(
            activity_type=ActivityType.CHAT,
            content=content,
            created_at=chat_data.get("event_timestamp", datetime.now()),
            metadata=metadata,
            weight=chat_data.get("weight", 1.0)
        )

    @staticmethod
    def quality_check_to_source_data(
        quality_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        품질 체크 결과를 소스 데이터로 변환

        Args:
            quality_metrics: 품질 메트릭

        Returns:
            변환된 소스 데이터
        """
        return {
            "quality_check": True,
            "quality_score": quality_metrics.get("quality_score", 0.0),
            "completeness_score": quality_metrics.get("completeness_score", 0.0),
            "freshness_score": quality_metrics.get("freshness_score", 0.0),
            "recommendations": quality_metrics.get("recommendations", []),
            "needs_update": quality_metrics.get("needs_update", False),
            "last_update_days": quality_metrics.get("last_update_days", 0),
            "timestamp": datetime.now().isoformat()
        }
