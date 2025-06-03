"""
메시지 큐 Publisher 서비스

다른 서비스로 메시지를 비동기적으로 전송하는 서비스입니다.
직접 API 호출 대신 메시지 큐를 통한 느슨한 결합을 구현합니다.
"""
import logging
import json
from typing import List, Dict

from aio_pika import connect_robust, DeliveryMode, Message
from aio_pika.exceptions import AMQPException

from app.core.config import settings
from app.models.message_models import BookmarkRelationshipMessage

log = logging.getLogger(__name__)

class MessagePublisher:
    """메시지 큐 Publisher 서비스"""

    def __init__(self):
        self.connection = None
        self.channel = None

    async def _get_connection(self):
        """RabbitMQ 연결 획득"""
        if not self.connection or self.connection.is_closed:
            self.connection = await connect_robust(settings.RABBITMQ_URL)
            self.channel = await self.connection.channel()
        return self.connection, self.channel

    async def publish_bookmark_relationships(
        self,
        user_id: int,
        source_bookmark: Dict,
        similar_bookmarks: List[Dict]
    ) -> bool:
        """
        북마크 관계 데이터를 메시지 큐로 전송합니다.
        
        Args:
            user_id: 사용자 ID
            source_bookmark: 소스 북마크 정보
            similar_bookmarks: 유사한 북마크들과 유사도 정보
            
        Returns:
            bool: 전송 성공 여부
        """
        try:
            # 메시지 데이터 준비
            message_data = BookmarkRelationshipMessage(
                user_id=user_id,
                source_bookmark=source_bookmark,
                similar_bookmarks=similar_bookmarks
            )

            # 메시지 전송
            success = await self._publish_message(
                queue_name=settings.BOOKMARK_RELATIONSHIP_QUEUE,
                message_data=message_data.model_dump(),
                routing_key="bookmark.relationship.create"
            )

            if success:
                log.info(
                    "북마크 관계 메시지 전송 성공 - user_id=%s, bookmark_id=%s, 관계수=%d",
                    user_id,
                    source_bookmark.get("bookmark_id"),
                    len(similar_bookmarks)
                )
            else:
                log.error(
                    "북마크 관계 메시지 전송 실패 - user_id=%s, bookmark_id=%s",
                    user_id,
                    source_bookmark.get("bookmark_id")
                )

            return success

        except (AMQPException, ValueError, TypeError) as e:  # pylint: disable=broad-exception-caught
            log.error("북마크 관계 메시지 발행 중 오류: %s", e)
            return False

    async def _publish_message(
        self,
        queue_name: str,
        message_data: Dict,
        routing_key: str = ""
    ) -> bool:
        """
        메시지를 지정된 큐로 발행합니다.
        
        Args:
            queue_name: 대상 큐 이름
            message_data: 전송할 메시지 데이터
            routing_key: 라우팅 키
            
        Returns:
            bool: 발행 성공 여부
        """
        try:
            _connection, channel = await self._get_connection()

            # 큐 선언 (durable=True로 설정하여 서버 재시작 시에도 보존)
            _ = await channel.declare_queue(
                queue_name,
                durable=True
            )

            # 메시지 생성
            message_body = json.dumps(message_data, ensure_ascii=False)
            message = Message(
                message_body.encode('utf-8'),
                delivery_mode=DeliveryMode.PERSISTENT,  # 메시지 영속성
                headers={
                    "content_type": "application/json",
                    "routing_key": routing_key
                }
            )

            # 메시지 발행
            await channel.default_exchange.publish(
                message,
                routing_key=queue_name
            )

            log.debug("메시지 발행 성공 - queue=%s, routing_key=%s", queue_name, routing_key)
            return True

        except (AMQPException, json.JSONDecodeError, UnicodeEncodeError) as e:  # pylint: disable=broad-exception-caught
            log.error("메시지 발행 중 오류 (queue=%s): %s", queue_name, e)
            return False

    async def close(self):
        """연결 종료"""
        try:
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
        except Exception as e:  # pylint: disable=broad-exception-caught
            log.warning("연결 종료 중 오류: %s", e)

# 전역 Publisher 인스턴스
message_publisher = MessagePublisher()
