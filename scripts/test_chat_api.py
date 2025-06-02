"""
PostgreSQL 연동 채팅 API 테스트 스크립트

1. 채팅 스트림 테스트
2. 세션 조회 테스트
3. 메시지 히스토리 테스트
"""
import asyncio
import aiohttp
import json
import sys
import os
from typing import Dict, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger


class ChatAPITester:
    """채팅 API 테스터"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session: aiohttp.ClientSession = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def test_chat_stream(self, user_id: int = 123, message: str = "안녕하세요!"):
        """채팅 스트림 API 테스트"""
        logger.info(f"🧪 채팅 스트림 테스트 시작 - user_id: {user_id}")
        
        url = f"{self.base_url}/chat/stream"
        payload = {
            "user_id": user_id,
            "message": message
        }
        
        try:
            async with self.session.post(
                url, 
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    logger.error(f"❌ API 호출 실패: {response.status}")
                    text = await response.text()
                    logger.error(f"응답: {text}")
                    return None
                
                logger.info("✅ 스트림 연결 성공!")
                
                full_response = ""
                session_id = None
                message_id = None
                
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if line.startswith('data: '):
                        data = line[6:]  # "data: " 제거
                        
                        try:
                            parsed = json.loads(data)
                            event_type = parsed.get('type')
                            
                            if event_type == 'chunk':
                                content = parsed.get('data', '')
                                full_response += content
                                print(content, end='', flush=True)  # 실시간 출력
                                
                            elif event_type == 'end':
                                session_id = parsed.get('session_id')
                                message_id = parsed.get('message_id')
                                logger.info(f"\n✅ 스트림 완료!")
                                logger.info(f"   세션 ID: {session_id}")
                                logger.info(f"   메시지 ID: {message_id}")
                                break
                                
                            elif event_type == 'error':
                                error_msg = parsed.get('data', 'Unknown error')
                                logger.error(f"❌ 스트림 에러: {error_msg}")
                                return None
                                
                        except json.JSONDecodeError:
                            continue  # 파싱 실패한 라인은 무시
                
                return {
                    "session_id": session_id,
                    "message_id": message_id,
                    "response": full_response
                }
                
        except Exception as e:
            logger.error(f"❌ 채팅 스트림 테스트 실패: {e}")
            return None
    
    async def test_get_sessions(self, user_id: int):
        """세션 목록 조회 테스트"""
        logger.info(f"🧪 세션 목록 조회 테스트 - user_id: {user_id}")
        
        url = f"{self.base_url}/chat/sessions"
        params = {"user_id": user_id, "limit": 10}
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ 세션 조회 실패: {response.status}")
                    return None
                
                data = await response.json()
                sessions = data.get('sessions', [])
                
                logger.info(f"✅ 세션 조회 성공! {len(sessions)}개 세션 발견")
                for session in sessions:
                    logger.info(f"   - {session['id']}: {session['title']}")
                
                return sessions
                
        except Exception as e:
            logger.error(f"❌ 세션 조회 테스트 실패: {e}")
            return None
    
    async def test_get_messages(self, session_id: str, user_id: int):
        """메시지 히스토리 조회 테스트"""
        logger.info(f"🧪 메시지 히스토리 조회 테스트 - session_id: {session_id}")
        
        url = f"{self.base_url}/chat/sessions/{session_id}/messages"
        params = {"user_id": user_id}
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ 메시지 조회 실패: {response.status}")
                    return None
                
                data = await response.json()
                messages = data.get('messages', [])
                
                logger.info(f"✅ 메시지 조회 성공! {len(messages)}개 메시지 발견")
                for msg in messages:
                    role = msg['role']
                    content = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
                    logger.info(f"   - [{role}]: {content}")
                
                return messages
                
        except Exception as e:
            logger.error(f"❌ 메시지 조회 테스트 실패: {e}")
            return None


async def main():
    """메인 테스트 함수"""
    logger.info("🚀 PostgreSQL 연동 채팅 API 테스트 시작")
    logger.info("="*60)
    
    async with ChatAPITester() as tester:
        test_user_id = 123
        test_message = "PostgreSQL 연동이 잘 되었는지 테스트해주세요!"
        
        # 1. 채팅 스트림 테스트
        logger.info("1️⃣ 채팅 스트림 테스트")
        result = await tester.test_chat_stream(test_user_id, test_message)
        
        if not result:
            logger.error("💥 채팅 스트림 테스트 실패!")
            return False
        
        session_id = result["session_id"]
        
        logger.info("="*30)
        
        # 2. 세션 목록 조회 테스트
        logger.info("2️⃣ 세션 목록 조회 테스트")
        sessions = await tester.test_get_sessions(test_user_id)
        
        if not sessions:
            logger.error("💥 세션 조회 테스트 실패!")
            return False
        
        logger.info("="*30)
        
        # 3. 메시지 히스토리 조회 테스트
        logger.info("3️⃣ 메시지 히스토리 조회 테스트")
        messages = await tester.test_get_messages(session_id, test_user_id)
        
        if not messages:
            logger.error("💥 메시지 조회 테스트 실패!")
            return False
        
        logger.info("="*60)
        logger.info("🎉 모든 테스트 통과!")
        logger.info("📋 테스트 결과:")
        logger.info(f"   - 생성된 세션 ID: {session_id}")
        logger.info(f"   - 총 세션 수: {len(sessions)}")
        logger.info(f"   - 총 메시지 수: {len(messages)}")
        
        return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 