"""
User Action Event Listeners

사용자 행동 이벤트를 감지하고 실시간 프로필 업데이트를 트리거하는 리스너들
"""

import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from loguru import logger

from app.services.user_profile_processor import UserProfileProcessor


class BookmarkEventListener:
    """북마크 이벤트를 처리하는 리스너"""

    def __init__(self, user_profile_processor: UserProfileProcessor):
        """
        BookmarkEventListener 초기화

        Args:
            user_profile_processor: 사용자 프로필 처리기
        """
        self.profile_processor = user_profile_processor
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

            # UserProfileProcessor를 통해 프로필 업데이트
            result = await self.profile_processor.handle_bookmark_event(
                user_id=user_id,
                bookmark_data=bookmark_data
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

            # 프로필 업데이트 실행
            result = await self.profile_processor.handle_bookmark_event(
                user_id=user_id,
                bookmark_data=bookmark_data
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
        logger.info(f"📞 콜백 등록됨 - Event Type: {event_type}")

    def stop_listening(self):
        """이벤트 감지를 중단합니다."""
        self._is_listening = False
        logger.info("🛑 북마크 이벤트 리스너 중단 요청")


class ChatEventListener:
    """채팅 이벤트를 처리하는 리스너 (향후 Task 32.2에서 구현)"""

    def __init__(self, user_profile_processor: UserProfileProcessor):
        """
        ChatEventListener 초기화

        Args:
            user_profile_processor: 사용자 프로필 처리기
        """
        self.profile_processor = user_profile_processor
        self.event_callbacks: Dict[str, Callable] = {}

    async def handle_chat_session_created(
        self,
        user_id: int,
        session_data: Dict[str, Any]  # pylint: disable=unused-argument
    ) -> Dict[str, Any]:
        """
        채팅 세션 생성 이벤트를 처리합니다.
        현재는 플레이스홀더로, Task 32.2에서 구현 예정

        Args:
            user_id: 사용자 ID
            session_data: 채팅 세션 데이터

        Returns:
            처리 결과
        """
        logger.info(f"💬 채팅 세션 생성 이벤트 - User ID: {user_id} (구현 예정)")
        return {
            "user_id": user_id,
            "event_type": "chat_session_created",
            "status": "placeholder",
            "message": "Task 32.2에서 구현 예정"
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
            chat_data: 채팅 세션 데이터
            metadata: 추가 메타데이터

        Returns:
            처리 결과
        """
        logger.info(f"💬 채팅 세션 완료 이벤트 처리 - User ID: {user_id}")

        try:
            # 메타데이터 추가
            if metadata:
                chat_data.update(metadata)

            # 이벤트 타임스탬프 추가
            chat_data["event_timestamp"] = datetime.now()
            chat_data["event_type"] = "chat_session_completed"

            # 채팅 세션이 프로필 업데이트에 충분한지 확인
            if not self._should_update_profile_for_chat(chat_data):
                logger.debug(f"프로필 업데이트 불필요 - User ID: {user_id}")
                return {
                    "user_id": user_id,
                    "event_type": "chat_session_completed",
                    "profile_updated": False,
                    "reason": "Chat session too short or insignificant"
                }

            # UserProfileProcessor를 통해 프로필 업데이트
            result = await self.profile_processor.handle_chat_completion_event(
                user_id=user_id,
                chat_data=chat_data
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

    def _should_update_profile_for_chat(self, chat_data: Dict[str, Any]) -> bool:
        """
        채팅 세션이 프로필 업데이트를 필요로 하는지 판단합니다.

        Args:
            chat_data: 채팅 세션 데이터

        Returns:
            프로필 업데이트 필요 여부
        """
        # 최소 메시지 수 확인
        message_count = chat_data.get("message_count", 0)
        if message_count < 3:  # 너무 짧은 대화는 제외
            return False

        # 최소 세션 지속 시간 확인 (30초 이상)
        duration = chat_data.get("duration", 0)
        if duration < 30:
            return False

        # 메시지가 있고 의미 있는 내용인지 확인
        messages = chat_data.get("messages", [])
        user_message_count = sum(1 for msg in messages if msg.get("role") == "user")
        if user_message_count < 2:  # 최소 2개의 사용자 메시지 필요
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
        logger.info(f"📞 채팅 콜백 등록됨 - Event Type: {event_type}")
