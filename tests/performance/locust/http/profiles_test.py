"""
프로필 관련 API 부하 테스트
"""

from locust import HttpUser, task, between
import sys
import os

# 공통 모듈 import를 위한 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common.test_data import generate_random_user_id
from common.base_user import BaseTestUser

class ProfileUser(HttpUser, BaseTestUser):
    wait_time = between(2, 5)  # 프로필 조회는 좀 더 여유있게
    
    def on_start(self):
        """사용자 세션 시작 시 실행"""
        BaseTestUser.__init__(self)
        self.user_id = generate_random_user_id()
    
    @task(4)
    def get_user_profile(self):
        """사용자 프로필 조회 (가중치 4)"""
        with self.client.get(
            f"/profile/{self.user_id}",
            timeout=10,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # 사용자가 없는 경우도 정상 응답으로 처리
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}")
    
    @task(2)
    def get_recommendations(self):
        """추천 조회 (가중치 2)"""
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
    
    @task(1)
    def get_analytics(self):
        """분석 데이터 조회 (가중치 1)"""
        with self.client.get(
            f"/analytics/{self.user_id}",
            timeout=20,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.success()
            else:
                response.failure(f"Status code: {response.status_code}") 