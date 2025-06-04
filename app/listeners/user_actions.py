"""
User Action Event Listeners

사용자 행동 이벤트를 감지하고 CQRS 기반 User Profile API를 통해
실시간 프로필 업데이트를 트리거하는 리스너들
"""

import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from loguru import logger

from app.services.user_profile_processor import UserProfileProcessor
from app.adapters.profile_api_adapter import (
    ProfileAPIAdapter,
    ProfileUpdateEventTranslator
)


class BookmarkEventListener:
    """북마크 이벤트를 처리하는 리스너"""

    def __init__(
        self,
        user_profile_processor: Optional[UserProfileProcessor] = None,
        use_api_adapter: bool = True
    ):
        """
        BookmarkEventListener 초기화

        Args:
            user_profile_processor: 사용자 프로필 처리기 (하위호환성)
            use_api_adapter: API 어댑터 사용 여부 (기본: True)
        """
        self.profile_processor = user_profile_processor
        self.use_api_adapter = use_api_adapter
        self.api_adapter = ProfileAPIAdapter() if use_api_adapter else None
        self.event_translator = ProfileUpdateEventTranslator()
        self.event_callbacks: Dict[str, Callable] = {}
        self._is_listening = False

    async def listen_bookmark_events(self, event_source: Optional[str] = None):
        """
        북마크 이벤트 감지를 시작합니다.

        Args:
            event_source: 이벤트 소스 (rabbitmq, webhook, database 등)
        """
        logger.info(f"🎧 북마크 이벤트 리스너 시작 - Source: {event_source or 'default'}")

        self._is_listening = True

        try:
            # 실제 환경에서는 RabbitMQ, Kafka, Webhook 등에서 이벤트를 수신
            # 여기서는 기본 구조만 구현
            while self._is_listening:
                # 이벤트 대기 (실제로는 메시지 큐에서 수신)
                await asyncio.sleep(0.1)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 북마크 이벤트 리스너 오류: {e}")
        finally:
            logger.info("🔇 북마크 이벤트 리스너 종료")

    async def handle_bookmark_created(
        self,
        user_id: int,
        bookmark_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        북마크 생성 이벤트를 처리합니다.

        Args:
            user_id: 사용자 ID
            bookmark_data: 북마크 데이터
            metadata: 추가 메타데이터

        Returns:
            처리 결과
        """
        logger.info(f"📖 북마크 생성 이벤트 처리 - User ID: {user_id}")

        try:
            # 메타데이터 추가
            if metadata:
                bookmark_data.update(metadata)

            # 이벤트 타임스탬프 추가
            bookmark_data["event_timestamp"] = datetime.now()
            bookmark_data["event_type"] = "bookmark_created"

            # API 어댑터를 통한 메시지 발행 (기본값)
            if self.use_api_adapter and self.api_adapter:
                result = await self._handle_via_api_adapter(
                    user_id, bookmark_data, "bookmark_created"
                )
            else:
                # 하위호환성: 직접 프로필 프로세서 호출
                result = await self._handle_via_direct_processor(
                    user_id, bookmark_data
                )

            # 콜백 실행 (있는 경우)
            if "bookmark_created" in self.event_callbacks:
                callback_result = await self.event_callbacks["bookmark_created"](
                    user_id, bookmark_data, result
                )
                result["callback_result"] = callback_result

            logger.info(f"✅ 북마크 생성 이벤트 처리 완료 - User ID: {user_id}")

            return result

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 북마크 생성 이벤트 처리 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "error": str(e),
                "user_id": user_id,
                "event_type": "bookmark_created",
                "timestamp": datetime.now()
            }

    async def handle_bookmark_updated(
        self,
        user_id: int,
        bookmark_data: Dict[str, Any],
        old_bookmark_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        북마크 수정 이벤트를 처리합니다.

        Args:
            user_id: 사용자 ID
            bookmark_data: 수정된 북마크 데이터
            old_bookmark_data: 이전 북마크 데이터

        Returns:
            처리 결과
        """
        logger.info(f"📝 북마크 수정 이벤트 처리 - User ID: {user_id}")

        try:
            # 변경 사항이 프로필에 영향을 미치는지 확인
            should_update_profile = self._should_update_profile_for_bookmark_change(
                bookmark_data, old_bookmark_data
            )

            if not should_update_profile:
                logger.debug(f"프로필 업데이트 불필요 - User ID: {user_id}")
                return {
                    "user_id": user_id,
                    "event_type": "bookmark_updated",
                    "profile_updated": False,
                    "reason": "No significant changes detected"
                }

            # 이벤트 메타데이터 추가
            bookmark_data["event_timestamp"] = datetime.now()
            bookmark_data["event_type"] = "bookmark_updated"
            if old_bookmark_data:
                bookmark_data["previous_data"] = old_bookmark_data

            # API 어댑터를 통한 메시지 발행 (기본값)
            if self.use_api_adapter and self.api_adapter:
                result = await self._handle_via_api_adapter(
                    user_id, bookmark_data, "bookmark_updated"
                )
            else:
                # 하위호환성: 직접 프로필 프로세서 호출
                result = await self._handle_via_direct_processor(
                    user_id, bookmark_data
                )

            logger.info(f"✅ 북마크 수정 이벤트 처리 완료 - User ID: {user_id}")

            return result

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 북마크 수정 이벤트 처리 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "error": str(e),
                "user_id": user_id,
                "event_type": "bookmark_updated",
                "timestamp": datetime.now()
            }

    async def _handle_via_api_adapter(
        self,
        user_id: int,
        bookmark_data: Dict[str, Any],
        update_type: str
    ) -> Dict[str, Any]:
        """
        API 어댑터를 통해 프로필 업데이트 메시지 발행

        Args:
            user_id: 사용자 ID
            bookmark_data: 북마크 데이터
            update_type: 업데이트 타입

        Returns:
            처리 결과
        """
        try:
            # 북마크 데이터를 ActivityData로 변환
            activity_data = self.event_translator.bookmark_event_to_activity_data(
                bookmark_data
            )

            # RabbitMQ를 통해 프로필 업데이트 메시지 발행
            success = await self.api_adapter.send_profile_update_message(
                user_id=user_id,
                activity_data=activity_data,
                update_type=update_type,
                metadata={
                    "source": "bookmark_event_listener",
                    "event_type": bookmark_data.get("event_type"),
                    "timestamp": datetime.now().isoformat()
                }
            )

            return {
                "success": success,
                "user_id": user_id,
                "event_type": update_type,
                "method": "api_adapter",
                "message_published": success,
                "timestamp": datetime.now()
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ API 어댑터 통한 처리 실패: {e}")
            raise

    async def _handle_via_direct_processor(
        self,
        user_id: int,
        bookmark_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        직접 프로필 프로세서를 통해 업데이트 (하위호환성)

        Args:
            user_id: 사용자 ID
            bookmark_data: 북마크 데이터

        Returns:
            처리 결과
        """
        if not self.profile_processor:
            raise ValueError("프로필 프로세서가 설정되지 않았습니다")

        # UserProfileProcessor를 통해 프로필 업데이트
        result = await self.profile_processor.handle_bookmark_event(
            user_id=user_id,
            bookmark_data=bookmark_data
        )

        result["method"] = "direct_processor"
        return result

    def _should_update_profile_for_bookmark_change(
        self,
        new_data: Dict[str, Any],
        old_data: Optional[Dict[str, Any]]
    ) -> bool:
        """
        북마크 변경이 프로필 업데이트를 필요로 하는지 판단합니다.

        Args:
            new_data: 새로운 북마크 데이터
            old_data: 이전 북마크 데이터

        Returns:
            프로필 업데이트 필요 여부
        """
        if not old_data:
            return True  # 이전 데이터가 없으면 업데이트

        # 중요한 필드들의 변경 사항 확인
        significant_fields = ["title", "description", "category", "tags", "content"]

        for field in significant_fields:
            if new_data.get(field) != old_data.get(field):
                logger.debug(f"중요 필드 변경 감지: {field}")
                return True

        return False

    def register_callback(self, event_type: str, callback: Callable):
        """
        이벤트 콜백을 등록합니다.

        Args:
            event_type: 이벤트 타입 (bookmark_created, bookmark_updated 등)
            callback: 콜백 함수
        """
        self.event_callbacks[event_type] = callback
        logger.debug(f"콜백 등록: {event_type}")

    def stop_listening(self):
        """이벤트 리스닝 중지"""
        self._is_listening = False
        logger.info("🔇 북마크 이벤트 리스너 중지 요청")


class ChatEventListener:
    """채팅 이벤트를 처리하는 리스너"""

    def __init__(
        self,
        user_profile_processor: Optional[UserProfileProcessor] = None,
        use_api_adapter: bool = True
    ):
        """
        ChatEventListener 초기화

        Args:
            user_profile_processor: 사용자 프로필 처리기 (하위호환성)
            use_api_adapter: API 어댑터 사용 여부 (기본: True)
        """
        self.profile_processor = user_profile_processor
        self.use_api_adapter = use_api_adapter
        self.api_adapter = ProfileAPIAdapter() if use_api_adapter else None
        self.event_translator = ProfileUpdateEventTranslator()
        self.event_callbacks: Dict[str, Callable] = {}

    async def handle_chat_session_created(
        self,
        user_id: int,
        session_data: Dict[str, Any]  # pylint: disable=unused-argument
    ) -> Dict[str, Any]:
        """
        채팅 세션 생성 이벤트를 처리합니다.

        Args:
            user_id: 사용자 ID
            session_data: 세션 데이터

        Returns:
            처리 결과
        """
        logger.info(f"💬 채팅 세션 생성 - User ID: {user_id}")

        # 세션 시작은 프로필 업데이트를 트리거하지 않음
        return {
            "user_id": user_id,
            "event_type": "chat_session_created",
            "profile_updated": False,
            "timestamp": datetime.now()
        }

    async def handle_chat_session_completed(
        self,
        user_id: int,
        chat_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        채팅 세션 완료 이벤트를 처리합니다.

        Args:
            user_id: 사용자 ID
            chat_data: 채팅 데이터
            metadata: 추가 메타데이터

        Returns:
            처리 결과
        """
        logger.info(f"🏁 채팅 세션 완료 이벤트 처리 - User ID: {user_id}")

        try:
            # 프로필 업데이트가 필요한지 확인
            should_update = self._should_update_profile_for_chat(chat_data)

            if not should_update:
                logger.debug(f"채팅으로 인한 프로필 업데이트 불필요 - User ID: {user_id}")
                return {
                    "user_id": user_id,
                    "event_type": "chat_session_completed",
                    "profile_updated": False,
                    "reason": "Chat session not significant enough for profile update"
                }

            # 메타데이터 추가
            if metadata:
                chat_data.update(metadata)

            chat_data["event_timestamp"] = datetime.now()
            chat_data["event_type"] = "chat_session_completed"

            # API 어댑터를 통한 메시지 발행 (기본값)
            if self.use_api_adapter and self.api_adapter:
                result = await self._handle_via_api_adapter(
                    user_id, chat_data, "chat_completed"
                )
            else:
                # 하위호환성: 직접 프로필 프로세서 호출
                result = await self._handle_via_direct_processor(
                    user_id, chat_data
                )

            # 콜백 실행 (있는 경우)
            if "chat_session_completed" in self.event_callbacks:
                callback_result = await self.event_callbacks["chat_session_completed"](
                    user_id, chat_data, result
                )
                result["callback_result"] = callback_result

            logger.info(f"✅ 채팅 세션 완료 이벤트 처리 완료 - User ID: {user_id}")

            return result

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 채팅 세션 완료 이벤트 처리 실패 - User ID: {user_id}, 오류: {e}")
            return {
                "error": str(e),
                "user_id": user_id,
                "event_type": "chat_session_completed",
                "timestamp": datetime.now()
            }

    async def _handle_via_api_adapter(
        self,
        user_id: int,
        chat_data: Dict[str, Any],
        update_type: str
    ) -> Dict[str, Any]:
        """
        API 어댑터를 통해 프로필 업데이트 메시지 발행

        Args:
            user_id: 사용자 ID
            chat_data: 채팅 데이터
            update_type: 업데이트 타입

        Returns:
            처리 결과
        """
        try:
            # 채팅 데이터를 ActivityData로 변환
            activity_data = self.event_translator.chat_event_to_activity_data(
                chat_data
            )

            # RabbitMQ를 통해 프로필 업데이트 메시지 발행
            success = await self.api_adapter.send_profile_update_message(
                user_id=user_id,
                activity_data=activity_data,
                update_type=update_type,
                metadata={
                    "source": "chat_event_listener",
                    "event_type": chat_data.get("event_type"),
                    "timestamp": datetime.now().isoformat()
                }
            )

            return {
                "success": success,
                "user_id": user_id,
                "event_type": update_type,
                "method": "api_adapter",
                "message_published": success,
                "timestamp": datetime.now()
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ API 어댑터 통한 처리 실패: {e}")
            raise

    async def _handle_via_direct_processor(
        self,
        user_id: int,
        chat_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        직접 프로필 프로세서를 통해 업데이트 (하위호환성)

        Args:
            user_id: 사용자 ID
            chat_data: 채팅 데이터

        Returns:
            처리 결과
        """
        if not self.profile_processor:
            raise ValueError("프로필 프로세서가 설정되지 않았습니다")

        # UserProfileProcessor를 통해 프로필 업데이트
        result = await self.profile_processor.handle_chat_completion_event(
            user_id=user_id,
            chat_data=chat_data
        )

        result["method"] = "direct_processor"
        return result

    def _should_update_profile_for_chat(self, chat_data: Dict[str, Any]) -> bool:
        """
        채팅이 프로필 업데이트를 필요로 하는지 판단합니다.

        Args:
            chat_data: 채팅 데이터

        Returns:
            프로필 업데이트 필요 여부
        """
        # 메시지 수가 너무 적으면 스킵
        messages = chat_data.get("messages", [])
        if len(messages) < 3:
            return False

        # 세션 시간이 너무 짧으면 스킵
        session_duration = chat_data.get("session_duration_minutes", 0)
        if session_duration < 2:
            return False

        # 사용자 메시지 비율 확인
        user_messages = [m for m in messages if m.get("role") == "user"]
        if len(user_messages) / len(messages) < 0.3:
            return False

        return True

    def register_callback(self, event_type: str, callback: Callable):
        """
        이벤트 콜백을 등록합니다.

        Args:
            event_type: 이벤트 타입
            callback: 콜백 함수
        """
        self.event_callbacks[event_type] = callback
        logger.debug(f"콜백 등록: {event_type}")

    async def close_connections(self):
        """연결 종료"""
        if self.api_adapter:
            await self.api_adapter.close_connection()
