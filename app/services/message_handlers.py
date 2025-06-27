"""
RabbitMQ 메시지 핸들러 - Command Side (CQRS)

Spring Boot 서버에서 보내는 비동기 작업 요청을 처리
- 프로필 업데이트 (백그라운드)
- 프로필 재생성 (장시간 작업)
- 추천 갱신 (캐시 갱신)
"""

import json
from datetime import datetime
from typing import Dict, Any

import aio_pika
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.tasks.user_profile_tasks import (
    UserProfileProcessor,
    create_repositories,
)
from app.services.vector_generator import VectorGenerator
from app.external.openai_service import OpenAIService
from app.schemas.profile_schemas import (
    ProfileUpdateRequest,
    ProfileRefreshRequest,
    RecommendationRefreshRequest,
    ActivityData
)


class ProfileMessageHandler:
    """프로필 관련 MQ 메시지 핸들러"""

    def __init__(self):
        self.openai_service = OpenAIService()
        self.vector_generator = VectorGenerator(self.openai_service)

    async def handle_profile_update(self, message_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        프로필 업데이트 메시지 처리

        Spring Boot에서 북마크 추가, 채팅 등의 이벤트 발생 시 호출
        백그라운드에서 점진적으로 프로필 업데이트
        """
        session_generator = get_async_session()
        async for session in session_generator:
            try:
                # 메시지 검증
                request = ProfileUpdateRequest(**message_body)
                logger.info(f"프로필 업데이트 요청 수신: user_id={request.user_id}")

                # Repository 생성
                repos = create_repositories()
                processor = UserProfileProcessor(
                    chat_repo=repos['chat_repo'],
                    bookmark_repo=repos['bookmark_repo'],
                    ai_profile_repo=repos['ai_profile_repo'],
                    user_profile_repo=repos['user_profile_repo']
                )

                # 점진적 업데이트 실행
                if request.incremental_update and request.source_data:
                    # 기존 프로필 조회
                    existing_profile = await repos['user_profile_repo'].get_or_create_profile(
                        session, request.user_id
                    )

                    # 새로운 데이터만으로 벡터 업데이트
                    # 기존 벡터가 None이거나 비어있으면 기본 벡터 사용
                    current_vector = existing_profile.profile_vector
                    if current_vector is None or (hasattr(current_vector, '__len__') and len(current_vector) == 0):
                        current_vector = [0.0] * 1536
                    
                    # 새로운 활동 데이터 준비 (source_data에서 추출)
                    new_activities = []
                    if request.source_data:
                        for activity_data in request.source_data:
                            new_activities.append({
                                'activity_type': activity_data.activity_type,
                                'content': activity_data.content,
                                'timestamp': activity_data.timestamp,
                                'metadata': activity_data.metadata,
                                'weight': activity_data.weight
                            })
                    
                    # 증분 업데이트 실행
                    result = await processor.update_vector_incrementally(
                        session,
                        user_id=request.user_id,
                        current_vector=current_vector,
                        learning_rate=0.1
                    )
                    
                    result_vector = result[0] if result else None
                    result_metadata = result[1] if len(result) > 1 else {}

                    # 결과에서 필요한 값 추출
                    result = {
                        "vector_strength": result_metadata.get("vector_strength", 0.0),
                        "processing_time": result_metadata.get("processing_time", 0.0)
                    }
                else:
                    # 전체 데이터 재수집하여 업데이트 - user_profile_tasks의 방식 사용
                    interests_data = await processor.extract_user_interests(session, request.user_id)
                    result_vector = await processor.generate_profile_vector(interests_data)
                    
                    # 프로필 업데이트
                    await repos['user_profile_repo'].update_profile(
                        session,
                        request.user_id,
                        keywords_frequency=interests_data.get("keyword_frequency", {}),
                        categories_distribution=interests_data.get("category_distribution", {}),
                        activity_patterns=interests_data.get("activity_patterns", {}),
                        profile_vector=result_vector,
                        data_sources_count=interests_data.get("data_sources", {}),
                        preferences={}
                    )
                    
                    result_metadata = {
                        "vector_strength": float(sum(x*x for x in result_vector)**0.5) if result_vector else 0.0,
                        "processing_time": 0.0,
                        "keywords_count": len(interests_data.get("keywords", [])),
                        "categories_count": len(interests_data.get("categories", []))
                    }

                # 수동 관심사 조정 처리
                if request.preference_adjustments:
                    await self._apply_preference_adjustments(
                        session, request.user_id, request.preference_adjustments
                    )

                logger.info(
                    f"프로필 업데이트 완료: user_id={request.user_id}, result={result}"
                )

                return {
                    "success": True,
                    "user_id": request.user_id,
                    "update_type": "incremental" if request.incremental_update else "full",
                    "vector_strength": result.get("vector_strength", 0.0),
                    "processing_time": result.get("processing_time", 0.0)
                }

            except (ValueError, KeyError, TypeError) as e:
                logger.error(f"프로필 업데이트 실패: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "user_id": message_body.get("user_id")
                }

    async def handle_profile_refresh(self, message_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        프로필 재생성 메시지 처리

        알고리즘 업데이트, 데이터 마이그레이션, 사용자 요청 시 호출
        전체 프로필을 처음부터 재계산 (장시간 작업)
        """
        # 작업 상태 초기화 (Redis 등에 저장)
        request = ProfileRefreshRequest(**message_body)
        logger.info(
            f"프로필 재생성 요청 수신: user_id={request.user_id}, job_id={request.job_id}"
        )

        await self._update_job_status(request.job_id, {
            "status": "IN_PROGRESS",
            "progress_percentage": 0,
            "started_at": datetime.now(),
            "user_id": request.user_id
        })

        session_generator = get_async_session()
        async for session in session_generator:
            try:
                repos = create_repositories()
                processor = UserProfileProcessor(
                    chat_repo=repos['chat_repo'],
                    bookmark_repo=repos['bookmark_repo'],
                    ai_profile_repo=repos['ai_profile_repo'],
                    user_profile_repo=repos['user_profile_repo']
                )

                # 기존 프로필 백업 (옵션)
                if request.force_full_recalculation:
                    await self._backup_existing_profile(session, request.user_id)

                # 진행 상태 업데이트
                await self._update_job_status(request.job_id, {
                    "progress_percentage": 25,
                    "current_step": "데이터 수집 중"
                })

                # 전체 프로필 재생성
                interests_data = await processor.extract_user_interests(session, request.user_id)
                result_vector = await processor.generate_profile_vector(interests_data)
                
                # 프로필 업데이트
                await repos['user_profile_repo'].update_profile(
                    session,
                    request.user_id,
                    keywords_frequency=interests_data.get("keyword_frequency", {}),
                    categories_distribution=interests_data.get("category_distribution", {}),
                    activity_patterns=interests_data.get("activity_patterns", {}),
                    profile_vector=result_vector,
                    data_sources_count=interests_data.get("data_sources", {}),
                    preferences={}
                )
                
                result_metadata = {
                    "vector_strength": float(sum(x*x for x in result_vector)**0.5) if result_vector else 0.0,
                    "processing_time": 0.0,
                    "keywords_count": len(interests_data.get("keywords", [])),
                    "categories_count": len(interests_data.get("categories", []))
                }

                # 의존성 재계산 (유사도, 추천 등)
                if "similarities" in request.recalculate_dependencies:
                    await processor.user_profile_repo.get_similar_users(
                        session, request.user_id, min_similarity=0.7, limit=50
                    )

                if "recommendations" in request.recalculate_dependencies:
                    # 추천 생성 (간단한 형태로)
                    logger.info(f"추천 재생성 시작: user_id={request.user_id}")

                # 작업 완료
                await self._update_job_status(request.job_id, {
                    "status": "COMPLETED",
                    "progress_percentage": 100,
                    "completed_at": datetime.now(),
                    "result_data": result_metadata
                })

                logger.info(
                    f"프로필 재생성 완료: user_id={request.user_id}, job_id={request.job_id}"
                )

                return {
                    "success": True,
                    "job_id": request.job_id,
                    "user_id": request.user_id,
                    "result": result_metadata
                }

            except (ValueError, KeyError, TypeError) as e:
                logger.error(f"프로필 재생성 실패: {str(e)}")

                # 실패 상태 업데이트
                await self._update_job_status(request.job_id, {
                    "status": "FAILED",
                    "error_message": str(e),
                    "failed_at": datetime.now()
                })

                return {
                    "success": False,
                    "job_id": request.job_id,
                    "error": str(e)
                }

    async def handle_recommendation_refresh(self, message_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        추천 갱신 메시지 처리

        사용자가 추천 조회 시 캐시 미스인 경우 백그라운드에서 호출
        새로운 추천 생성하여 캐시 갱신
        """
        session_generator = get_async_session()
        async for session in session_generator:
            try:
                request = RecommendationRefreshRequest(**message_body)
                logger.info(f"추천 갱신 요청 수신: user_id={request.user_id}")

                repos = create_repositories()
                processor = UserProfileProcessor(
                    chat_repo=repos['chat_repo'],
                    bookmark_repo=repos['bookmark_repo'],
                    ai_profile_repo=repos['ai_profile_repo'],
                    user_profile_repo=repos['user_profile_repo']
                )

                # 사용자 프로필 조회
                profile = await repos['user_profile_repo'].get_or_create_profile(
                    session, request.user_id
                )
                if not profile:
                    return {
                        "success": False,
                        "error": "사용자 프로필을 찾을 수 없습니다",
                        "user_id": request.user_id
                    }

                # 유사한 사용자들을 기반으로 추천 생성 (단순화된 형태)
                similar_users = await repos['user_profile_repo'].get_similar_users(
                    session, request.user_id, min_similarity=0.7, limit=10
                )

                # 사용자 프로필 기반 추천 생성
                interests_data = await processor.extract_user_interests(session, request.user_id)
                
                # 간단한 추천 생성 (유사 사용자 기반)
                recommendations = []
                for user in similar_users:
                    recommendations.append({
                        "user_id": user.user_id,
                        "similarity_score": user.similarity_score,
                        "type": "user_similarity"
                    })

                logger.info(
                    f"추천 갱신 완료: user_id={request.user_id}, "
                    f"추천 수: {len(recommendations)}"
                )

                return {
                    "success": True,
                    "user_id": request.user_id,
                    "recommendations_count": len(recommendations),
                    "similar_users_count": len(similar_users),
                    "categories": request.categories or [],
                    "limit": request.limit
                }

            except (ValueError, KeyError, TypeError) as e:
                logger.error(f"추천 갱신 실패: {str(e)}")
                return {
                    "success": False,
                    "error": str(e),
                    "user_id": message_body.get("user_id")
                }

    async def _apply_preference_adjustments(
        self,
        session: AsyncSession,  # pylint: disable=unused-argument
        user_id: int,
        adjustments: Dict[str, float]
    ):
        """사용자 선호도 수동 조정 적용"""
        # repository를 직접 생성하는 대신 create_repositories 사용
        repos = create_repositories()
        user_profile_repo = repos['user_profile_repo']

        profile = await user_profile_repo.get_or_create_profile(session, user_id)
        if not profile or not profile.vector_metadata:
            return

        # 메타데이터에서 키워드 가중치 조정
        metadata = profile.vector_metadata.copy()
        keywords = metadata.get("keywords", {})

        for keyword, adjustment in adjustments.items():
            if keyword in keywords:
                keywords[keyword] = min(1.0, max(0.0, adjustment))

        metadata["keywords"] = keywords
        metadata["manual_adjustments"] = adjustments
        metadata["last_manual_update"] = datetime.now().isoformat()

        # 프로필 업데이트
        await user_profile_repo.update_profile(
            session,
            user_id,
            vector_metadata=metadata
        )

    async def _backup_existing_profile(self, session: AsyncSession, user_id: int):  # pylint: disable=unused-argument
        """기존 프로필 백업"""
        # 실제 구현에서는 별도 백업 테이블이나 스토리지에 저장
        logger.info(f"프로필 백업: user_id={user_id}")
        # TODO: 실제 백업 로직 구현 필요

    async def _update_job_status(self, job_id: str, status_data: Dict[str, Any]):
        """작업 상태 업데이트 (Redis 등에 저장)"""
        # 실제 구현에서는 Redis나 별도 작업 상태 저장소 사용
        logger.info(f"작업 상태 업데이트: job_id={job_id}, status={status_data}")
        # TODO: 실제 상태 저장 로직 구현 필요


class RabbitMQConsumer:  # pylint: disable=too-few-public-methods
    """RabbitMQ 컨슈머 설정 및 메시지 라우팅"""

    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self.handler = ProfileMessageHandler()
        self.connection = None
        self.channel = None

    async def setup_queues_and_consumers(self):
        """큐 설정 및 컨슈머 등록"""
        self.connection = await aio_pika.connect_robust(self.connection_url)
        self.channel = await self.connection.channel()

        try:
            # 프로필 업데이트 큐
            profile_update_queue = await self.channel.declare_queue(
                "profile.update.queue",
                durable=True,
                arguments={"x-message-ttl": 3600000}  # 1시간 TTL
            )
        except aio_pika.exceptions.ChannelPreconditionFailed:
            # 이미 존재하는 큐 사용 (설정 충돌 시)
            logger.warning("profile.update.queue 이미 존재함 - 기존 설정 사용")
            profile_update_queue = await self.channel.declare_queue(
                "profile.update.queue",
                durable=True,
                passive=True  # 기존 큐 사용
            )

        try:
            # 프로필 재생성 큐
            profile_refresh_queue = await self.channel.declare_queue(
                "profile.refresh.queue",
                durable=True,
                arguments={"x-message-ttl": 3600000}  # 1시간 TTL (기존과 동일)
            )
        except aio_pika.exceptions.ChannelPreconditionFailed:
            # 이미 존재하는 큐 사용 (설정 충돌 시)
            logger.warning("profile.refresh.queue 이미 존재함 - 기존 설정 사용")
            profile_refresh_queue = await self.channel.declare_queue(
                "profile.refresh.queue",
                durable=True,
                passive=True  # 기존 큐 사용
            )

        try:
            # 추천 갱신 큐
            recommendation_refresh_queue = await self.channel.declare_queue(
                "recommendation.refresh.queue",
                durable=True
            )
        except aio_pika.exceptions.ChannelPreconditionFailed:
            # 이미 존재하는 큐 사용 (설정 충돌 시)
            logger.warning("recommendation.refresh.queue 이미 존재함 - 기존 설정 사용")
            recommendation_refresh_queue = await self.channel.declare_queue(
                "recommendation.refresh.queue",
                durable=True,
                passive=True  # 기존 큐 사용
            )

        # 컨슈머 등록
        await profile_update_queue.consume(self._handle_profile_update_message)
        await profile_refresh_queue.consume(self._handle_profile_refresh_message)
        await recommendation_refresh_queue.consume(
            self._handle_recommendation_refresh_message
        )

        logger.info("RabbitMQ 컨슈머 설정 완료")
        return self.connection
    
    async def close_connection(self):
        """RabbitMQ 연결 정리"""
        try:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
                logger.info("RabbitMQ 채널 정리 완료")
        except Exception as e:
            logger.warning(f"RabbitMQ 채널 정리 중 오류: {e}")
        
        try:
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
                logger.info("RabbitMQ 연결 정리 완료")
        except Exception as e:
            logger.warning(f"RabbitMQ 연결 정리 중 오류: {e}")

    async def _handle_profile_update_message(self, message: aio_pika.IncomingMessage):
        """프로필 업데이트 메시지 처리 래퍼"""
        async with message.process():
            try:
                body = json.loads(message.body.decode())
                result = await self.handler.handle_profile_update(body)

                if result["success"]:
                    logger.info(f"프로필 업데이트 메시지 처리 성공: {result}")
                else:
                    logger.error(f"프로필 업데이트 메시지 처리 실패: {result}")

            except json.JSONDecodeError as e:
                logger.error(f"메시지 JSON 디코딩 오류: {str(e)}")
                raise
            except KeyError as e:
                logger.error(f"메시지 처리 중 키 오류: {str(e)}")
                raise

    async def _handle_profile_refresh_message(self, message: aio_pika.IncomingMessage):
        """프로필 재생성 메시지 처리 래퍼"""
        async with message.process():
            try:
                body = json.loads(message.body.decode())
                result = await self.handler.handle_profile_refresh(body)

                if result["success"]:
                    logger.info(f"프로필 재생성 메시지 처리 성공: {result}")
                else:
                    logger.error(f"프로필 재생성 메시지 처리 실패: {result}")

            except json.JSONDecodeError as e:
                logger.error(f"메시지 JSON 디코딩 오류: {str(e)}")
                raise
            except KeyError as e:
                logger.error(f"메시지 처리 중 키 오류: {str(e)}")
                raise

    async def _handle_recommendation_refresh_message(self,
                                                     message: aio_pika.IncomingMessage):
        """추천 갱신 메시지 처리 래퍼"""
        async with message.process():
            try:
                body = json.loads(message.body.decode())
                result = await self.handler.handle_recommendation_refresh(body)

                if result["success"]:
                    logger.info(f"추천 갱신 메시지 처리 성공: {result}")
                else:
                    logger.error(f"추천 갱신 메시지 처리 실패: {result}")

            except json.JSONDecodeError as e:
                logger.error(f"메시지 JSON 디코딩 오류: {str(e)}")
                raise
            except KeyError as e:
                logger.error(f"메시지 처리 중 키 오류: {str(e)}")
                raise
