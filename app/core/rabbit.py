"""
RabbitMQ 감륜 및 통신 모듈

이 모듈은 RabbitMQ와의 연결 및 메시지 관리를 위한 유틸리티 함수를 제공합니다.
비동기 연결 및 메시지 발행을 위한 함수를 포함합니다.
"""
import json
from aio_pika import connect_robust, Message, IncomingMessage
from app.core.config import settings

import logging
logger = logging.getLogger(__name__)

async def get_rabbit_connection():
    """
    RabbitMQ와의 강건한 연결을 생성합니다.
    
    구성 설정에서 RABBITMQ_URL을 사용하여 연결하고, 연결 실패 시 로그를 기록합니다.
    
    Returns:
        Connection: aio_pika RabbitMQ 연결 객체
        
    Raises:
        Exception: RabbitMQ 연결 중 오류가 발생한 경우
    """
    try:
        return await connect_robust(settings.RABBITMQ_URL)
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        raise

async def publish(channel, routing_key: str, payload: dict, **props):
    """
    RabbitMQ에 메시지를 발행합니다.
    
    주어진 채널과 라우팅 키를 사용하여 페이로드를 JSON으로 직렬화하고 기본 교환기를 통해 발행합니다.
    
    Args:
        channel: 메시지를 발행할 aio_pika 채널 객체
        routing_key (str): 메시지 라우팅 키
        payload (dict): 발행할 메시지 데이터
        **props: 추가 메시지 속성 (예: delivery_mode, headers 등)
    """
    
    await channel.default_exchange.publish(
        Message(body=json.dumps(payload).encode(), **props),
        routing_key=routing_key,
    )
