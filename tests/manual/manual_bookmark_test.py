#!/usr/bin/env python3
"""
실제 북마크 저장 수동 테스트 스크립트

이 스크립트는 실제 RabbitMQ에 메시지를 보내서 
북마크 저장 플로우를 테스트합니다.
"""

import json
import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.rabbit import get_rabbit_connection
import aio_pika
from app.core.config import settings


async def send_bookmark_message(message_data: dict):
    """실제 RabbitMQ에 북마크 저장 메시지 전송"""
    
    try:
        # RabbitMQ 연결
        connection = await get_rabbit_connection()
        channel = await connection.channel()
        
        # 큐 선언
        queue_name = settings.BOOKMARK_SAVE_QUEUE
        await channel.declare_queue(queue_name, durable=True)
        
        # 메시지 전송
        message_body = json.dumps(message_data).encode('utf-8')
        message = aio_pika.Message(
            message_body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        
        await channel.default_exchange.publish(
            message,
            routing_key=queue_name
        )
        
        print(f"✅ 메시지 전송 완료: {queue_name}")
        print(f"📄 메시지 내용: {json.dumps(message_data, indent=2, ensure_ascii=False)}")
        
        await connection.close()
        return True
        
    except Exception as e:
        print(f"❌ 메시지 전송 실패: {e}")
        return False


async def create_test_html_file():
    """테스트용 HTML 파일 생성"""
    
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI와 머신러닝 기초</title>
        <meta charset="utf-8">
    </head>
    <body>
        <h1>AI와 머신러닝 기초</h1>
        <p>인공지능(AI)은 현대 기술의 핵심 분야 중 하나입니다.</p>
        <p>머신러닝은 AI의 하위 분야로, 데이터에서 패턴을 학습하는 기술입니다.</p>
        <h2>주요 개념들</h2>
        <ul>
            <li>딥러닝: 신경망을 이용한 학습 방법</li>
            <li>지도학습: 라벨이 있는 데이터로 학습</li>
            <li>비지도학습: 라벨 없는 데이터에서 패턴 발견</li>
            <li>강화학습: 환경과의 상호작용을 통한 학습</li>
        </ul>
        <p>이러한 기술들은 자연어 처리, 컴퓨터 비전, 추천 시스템 등 
           다양한 분야에 적용되고 있습니다.</p>
    </body>
    </html>
    """
    
    # 로컬 테스트용 파일 저장
    test_file_path = project_root / "test_bookmark.html"
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_html)
    
    print(f"📁 테스트 HTML 파일 생성됨: {test_file_path}")
    return test_file_path


def get_sample_bookmark_data():
    """샘플 북마크 데이터 생성"""
    
    return {
        "userId": 123,
        "starId": f"manual_test_{int(asyncio.get_event_loop().time())}",
        "s3Key": "test/manual_test.html",  # 실제 S3가 없다면 로컬 파일로 대체
        "title": "AI와 머신러닝 기초 - 수동 테스트",
        "url": "https://example.com/ai-ml-basics",
        "keywords": ["AI", "머신러닝", "딥러닝", "인공지능", "테스트"],
        "memo": "실제 북마크 저장 테스트용 메모입니다.",
        "summary": "AI와 머신러닝의 기초 개념을 다루는 문서로, 딥러닝, 지도학습, 비지도학습, 강화학습 등의 주요 개념들을 설명합니다."
    }


async def consumer_only_test():
    """Consumer만 테스트 (Celery 없이) - pytest가 인식하지 않도록 이름 변경"""
    
    print("🧪 Consumer 단독 테스트 시작...")
    
    # 테스트 메시지 생성
    test_data = get_sample_bookmark_data()
    
    # 실제 Consumer 함수 호출
    from app.consumers.bookmark_save_rmq import on_bookmark_save
    
    class MockIncomingMessage:
        def __init__(self, payload):
            self.body = json.dumps(payload).encode('utf-8')
        
        def process(self):
            class MockContext:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return MockContext()
    
    message = MockIncomingMessage(test_data)
    await on_bookmark_save(message)
    
    print("✅ Consumer 테스트 완료")


async def task_directly_test():
    """Celery Task를 직접 테스트 - pytest가 인식하지 않도록 이름 변경"""
    
    print("🔧 Task 직접 테스트 시작...")
    
    # 테스트 데이터 (Task에서 기대하는 필드명으로 변환)
    test_data = get_sample_bookmark_data()
    
    # 필드명 변환: userId -> user_id, starId -> star_id 등
    task_data = {
        "user_id": test_data["userId"],
        "star_id": test_data["starId"],
        "s3_key": test_data["s3Key"],
        "title": test_data["title"],
        "url": test_data["url"],
        "keywords": test_data["keywords"],
        "memo": test_data["memo"],
        "summary": test_data["summary"]
    }
    
    try:
        # BookmarkData 생성 테스트만 수행 (asyncio 충돌 방지)
        from app.tasks.bookmark_save_task import BookmarkData
        
        bookmark_data = BookmarkData(**task_data)
        print(f"✅ BookmarkData 생성 성공:")
        print(f"   - user_id: {bookmark_data.user_id}")
        print(f"   - star_id: {bookmark_data.star_id}")
        print(f"   - title: {bookmark_data.title}")
        
        # 실제 태스크는 Celery Worker에서 실행되므로 직접 호출하지 않음
        print("📝 참고: 실제 태스크 실행은 Celery Worker에서 별도 프로세스로 처리됩니다.")
        print("📝 RabbitMQ 메시지 전송 테스트로 전체 플로우를 확인할 수 있습니다.")
        
    except Exception as e:
        print(f"⚠️ Task 준비 중 오류: {e}")


# pytest 인식을 방지하기 위한 별칭
test_consumer_only = consumer_only_test
test_task_directly = task_directly_test


async def main():
    """메인 테스트 함수"""
    
    print("🎯 북마크 저장 실제 테스트 시작!")
    print("=" * 50)
    
    # 1. 테스트 HTML 파일 생성
    await create_test_html_file()
    
    # 2. 테스트 방법 선택
    print("\n어떤 방식으로 테스트하시겠습니까?")
    print("1. RabbitMQ 메시지 전송 (전체 플로우)")
    print("2. Consumer 단독 테스트")
    print("3. Task 직접 실행")
    print("4. 모든 방법으로 테스트")
    
    choice = input("선택 (1-4): ").strip()
    
    if choice == "1":
        # RabbitMQ 메시지 전송
        test_data = get_sample_bookmark_data()
        success = await send_bookmark_message(test_data)
        if success:
            print("\n🎉 메시지 전송 완료! Consumer와 Celery Worker가 실행 중이라면 처리됩니다.")
        
    elif choice == "2":
        # Consumer 단독 테스트
        await test_consumer_only()
        
    elif choice == "3":
        # Task 직접 실행
        await test_task_directly()
        
    elif choice == "4":
        # 모든 방법 테스트
        print("\n1️⃣ Consumer 테스트...")
        await test_consumer_only()
        
        print("\n2️⃣ Task 직접 테스트...")
        await test_task_directly()
        
        print("\n3️⃣ RabbitMQ 메시지 전송...")
        test_data = get_sample_bookmark_data()
        await send_bookmark_message(test_data)
        
    else:
        print("❌ 잘못된 선택입니다.")
    
    print("\n✨ 테스트 완료!")


if __name__ == "__main__":
    # 환경 변수 로드 (선택적)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️ python-dotenv가 없습니다. 환경변수를 수동으로 설정해주세요.")
    
    asyncio.run(main())
