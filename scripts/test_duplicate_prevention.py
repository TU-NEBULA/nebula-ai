#!/usr/bin/env python3
"""
중복 메시지 방지 테스트 스크립트

동일한 요청을 빠르게 여러 번 보내서 중복 메시지가 생성되는지 확인합니다.
"""
import asyncio
import aiohttp
import json
import time
from concurrent.futures import ThreadPoolExecutor
import uuid

# API 기본 설정
API_BASE_URL = "http://localhost:8000"
TEST_USER_ID = 999
TEST_MESSAGE = "중복 테스트 메시지입니다"
REQUEST_COUNT = 5  # 동시에 보낼 요청 수

async def send_chat_request(session: aiohttp.ClientSession, request_id: int, idempotency_key: str = None):
    """채팅 요청을 보냅니다."""
    url = f"{API_BASE_URL}/chat/stream"
    headers = {
        "Content-Type": "application/json",
    }
    
    if idempotency_key:
        headers["idempotency-key"] = idempotency_key
    
    payload = {
        "user_id": TEST_USER_ID,
        "message": f"{TEST_MESSAGE} #{request_id}"
    }
    
    try:
        start_time = time.time()
        async with session.post(url, json=payload, headers=headers) as response:
            end_time = time.time()
            
            if response.status == 200:
                # SSE 스트림 읽기
                session_id = None
                message_id = None
                
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str.startswith('data: '):
                        data_json = line_str[6:]  # "data: " 제거
                        try:
                            data = json.loads(data_json)
                            if data.get('type') == 'session_end':
                                session_id = data.get('session_id')
                                message_id = data.get('ai_message_id')
                                break
                            elif data.get('type') == 'session_start':
                                session_id = data.get('data', {}).get('session_id')
                        except json.JSONDecodeError:
                            continue
                
                return {
                    "request_id": request_id,
                    "status": "success",
                    "session_id": session_id,
                    "message_id": message_id,
                    "response_time": end_time - start_time,
                    "idempotency_key": idempotency_key
                }
            else:
                return {
                    "request_id": request_id,
                    "status": "error",
                    "error": f"HTTP {response.status}",
                    "response_time": end_time - start_time,
                    "idempotency_key": idempotency_key
                }
                
    except Exception as e:
        return {
            "request_id": request_id,
            "status": "exception",
            "error": str(e),
            "idempotency_key": idempotency_key
        }

async def test_duplicate_prevention():
    """중복 방지 테스트를 실행합니다."""
    print("🧪 중복 메시지 방지 테스트 시작")
    print(f"📊 테스트 설정: {REQUEST_COUNT}개 동시 요청")
    print("-" * 60)
    
    async with aiohttp.ClientSession() as session:
        # 테스트 1: Idempotency Key 없이 동시 요청
        print("🔄 테스트 1: Idempotency Key 없이 동시 요청")
        tasks = []
        for i in range(REQUEST_COUNT):
            task = send_chat_request(session, i + 1)
            tasks.append(task)
        
        results1 = await asyncio.gather(*tasks)
        
        print("\n📋 결과 1:")
        unique_sessions = set()
        unique_messages = set()
        
        for result in results1:
            print(f"  요청 {result['request_id']}: {result['status']}")
            if result['status'] == 'success':
                print(f"    세션 ID: {result['session_id']}")
                print(f"    메시지 ID: {result['message_id']}")
                print(f"    응답시간: {result['response_time']:.3f}초")
                unique_sessions.add(result['session_id'])
                unique_messages.add(result['message_id'])
        
        print(f"\n📈 통계 1:")
        print(f"  총 요청 수: {REQUEST_COUNT}")
        print(f"  성공한 요청: {len([r for r in results1 if r['status'] == 'success'])}")
        print(f"  생성된 고유 세션: {len(unique_sessions)}")
        print(f"  생성된 고유 메시지: {len(unique_messages)}")
        
        print("\n" + "="*60)
        
        # 테스트 2: 동일한 Idempotency Key로 동시 요청
        print("🔄 테스트 2: 동일한 Idempotency Key로 동시 요청")
        idempotency_key = str(uuid.uuid4())
        
        tasks = []
        for i in range(REQUEST_COUNT):
            task = send_chat_request(session, i + 1, idempotency_key)
            tasks.append(task)
        
        results2 = await asyncio.gather(*tasks)
        
        print("\n📋 결과 2:")
        unique_sessions2 = set()
        unique_messages2 = set()
        
        for result in results2:
            print(f"  요청 {result['request_id']}: {result['status']}")
            if result['status'] == 'success':
                print(f"    세션 ID: {result['session_id']}")
                print(f"    메시지 ID: {result['message_id']}")
                print(f"    응답시간: {result['response_time']:.3f}초")
                print(f"    Idempotency Key: {result['idempotency_key']}")
                unique_sessions2.add(result['session_id'])
                unique_messages2.add(result['message_id'])
        
        print(f"\n📈 통계 2:")
        print(f"  총 요청 수: {REQUEST_COUNT}")
        print(f"  성공한 요청: {len([r for r in results2 if r['status'] == 'success'])}")
        print(f"  생성된 고유 세션: {len(unique_sessions2)}")
        print(f"  생성된 고유 메시지: {len(unique_messages2)}")

async def check_database_messages():
    """데이터베이스에서 실제 메시지 개수를 확인합니다."""
    print("\n🔍 데이터베이스 메시지 확인")
    print("-" * 60)
    
    # PostgreSQL 연결 정보는 환경변수에서 가져옴
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    try:
        import asyncpg
        
        db_url = (
            f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
            f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
        )
        
        conn = await asyncpg.connect(db_url)
        
        # 테스트 메시지 개수 확인
        query = """
        SELECT 
            content,
            role,
            user_id,
            COUNT(*) as count,
            string_agg(id::text, ', ') as message_ids
        FROM chat_messages 
        WHERE user_id = $1 AND content LIKE $2
        GROUP BY content, role, user_id
        ORDER BY COUNT(*) DESC;
        """
        
        rows = await conn.fetch(query, str(TEST_USER_ID), f"{TEST_MESSAGE}%")
        
        print("📊 중복 메시지 통계:")
        total_duplicates = 0
        for row in rows:
            count = row['count']
            if count > 1:
                total_duplicates += count - 1
                print(f"  ⚠️  중복: '{row['content'][:50]}...' ({count}개)")
                print(f"      메시지 IDs: {row['message_ids']}")
            else:
                print(f"  ✅  정상: '{row['content'][:50]}...' (1개)")
        
        print(f"\n📈 전체 통계:")
        print(f"  총 메시지 수: {sum(row['count'] for row in rows)}")
        print(f"  중복 메시지 수: {total_duplicates}")
        
        await conn.close()
        
    except ImportError:
        print("❌ asyncpg 라이브러리가 설치되지 않았습니다.")
        print("   pip install asyncpg 로 설치해주세요.")
    except Exception as e:
        print(f"❌ 데이터베이스 연결 오류: {e}")

if __name__ == "__main__":
    print("🚀 중복 메시지 방지 테스트 도구")
    print("="*60)
    
    asyncio.run(test_duplicate_prevention())
    asyncio.run(check_database_messages())
    
    print("\n✅ 테스트 완료") 