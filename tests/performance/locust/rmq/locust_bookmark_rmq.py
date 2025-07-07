from locust import User, task, between, events
import pika
import json
import time
import os
import sys

# 공통 모듈 import를 위한 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common.test_data import (
    generate_bookmark_payload, 
    generate_extract_data_payload,
    generate_random_user_id
)
from common.base_user import BaseTestUser, create_timer

# 환경 변수
AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@rabbitmq:5672/%2f")
BOOKMARK_EXCHANGE = "bookmark_exchange"
BOOKMARK_ROUTING_KEY = "bookmark.create"
EXTRACT_EXCHANGE = "extract_exchange"
EXTRACT_ROUTING_KEY = "extract.data"

class BookmarkPublisher(User, BaseTestUser):
    wait_time = between(0.1, 0.5)  # RabbitMQ 메시지 간 짧은 간격
    
    def on_start(self):
        """RabbitMQ 연결 설정"""
        BaseTestUser.__init__(self)
        self.user_id = generate_random_user_id()
        try:
            params = pika.URLParameters(AMQP_URL)
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            
            # Exchange와 Queue 존재 확인 (passive=True로 선언하지 않고 확인만)
            # 실제 환경에서는 이미 설정되어 있을 것으로 가정
            print(f"Connected to RabbitMQ: {AMQP_URL}")
            
        except Exception as e:
            print(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def on_stop(self):
        """연결 종료"""
        if hasattr(self, 'connection') and self.connection:
            self.connection.close()
    
    @task
    def publish_bookmark_create(self):
        """북마크 생성 메시지 발행"""
        bookmark_data = generate_bookmark_payload(self.user_id)
        bookmark_data["created_at"] = time.time()  # 실제 전송 시점 설정
        
        message_body = json.dumps(bookmark_data)
        
        with create_timer(self, "RMQ", "bookmark.create"):
            # 메시지 발행
            self.channel.basic_publish(
                exchange=BOOKMARK_EXCHANGE,
                routing_key=BOOKMARK_ROUTING_KEY,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # 메시지 지속성
                    content_type='application/json'
                )
            )
    
    @task(weight=2)
    def publish_extract_data(self):
        """데이터 추출 메시지 발행 (가중치 2)"""
        extract_data = generate_extract_data_payload(self.user_id)
        message_body = json.dumps(extract_data)
        
        with create_timer(self, "RMQ", "extract.data"):
            self.channel.basic_publish(
                exchange=EXTRACT_EXCHANGE,
                routing_key=EXTRACT_ROUTING_KEY,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            ) 