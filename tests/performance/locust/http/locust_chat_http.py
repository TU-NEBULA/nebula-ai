from locust import HttpUser, task, between
import sys
import os

# 공통 모듈 import를 위한 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common.test_data import generate_chat_payload, generate_random_user_id, generate_session_id
from common.base_user import BaseTestUser

class ChatUser(HttpUser, BaseTestUser):
    wait_time = between(1, 3)  # 요청 간 1-3초 대기
    
    def on_start(self):
        """사용자 세션 시작 시 실행"""
        BaseTestUser.__init__(self)
        self.user_id = generate_random_user_id()
        self.session_id = generate_session_id()
    
    @task(3)
    def stream_chat(self):
        """채팅 스트림 요청 (가중치 3)"""
        payload = generate_chat_payload(self.user_id, self.session_id)
        
        with self.client.post(
            "/chat/stream",
            json=payload,
            timeout=30,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_profile(self):
        """사용자 프로필 조회 (가중치 1)"""
        with self.client.get(
            f"/profile/{self.user_id}",
            timeout=10,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # 프로필이 없는 경우는 정상으로 간주
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(1)
    def get_recommendations(self):
        """추천 조회 (가중치 1)"""
        with self.client.get(
            f"/recommendations/{self.user_id}",
            timeout=15,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}") 