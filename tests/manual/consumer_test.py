#!/usr/bin/env python3
"""
Consumer 단독 테스트 스크립트

북마크 저장 Consumer의 메시지 처리 기능만 독립적으로 테스트합니다.
"""

import json
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.consumers.bookmark_save_rmq import on_bookmark_save
from tests.manual.data_helper import get_test_scenarios


class MockIncomingMessage:
    """테스트용 Mock 메시지 클래스"""
    
    def __init__(self, payload: dict):
        self.body = json.dumps(payload).encode('utf-8')
    
    def process(self):
        class MockContext:
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        return MockContext()


async def run_consumer_test_case(test_case: dict):
    """개별 테스트 케이스를 실행"""
    
    print(f"\n🧪 테스트: {test_case['name']}")
    print("-" * 50)
    
    message = MockIncomingMessage(test_case['data'])
    
    try:
        await on_bookmark_save(message)
        
        if test_case.get('should_succeed', True):
            print("✅ 테스트 성공 - 예상대로 처리됨")
            return True
        else:
            print("❌ 테스트 실패 - 오류가 발생해야 했지만 정상 처리됨")
            return False
            
    except Exception as e:
        if not test_case.get('should_succeed', True):
            print(f"✅ 테스트 성공 - 예상대로 오류 발생: {type(e).__name__}")
            return True
        else:
            print(f"❌ 테스트 실패 - 예상치 못한 오류: {e}")
            return False


async def run_json_parsing_test():
    """JSON 파싱 오류 테스트"""
    
    print("\n🧪 테스트: JSON 파싱 오류")
    print("-" * 50)
    
    class BadJsonMessage:
        def __init__(self):
            self.body = b'{"invalid": json, "data": true}'  # 잘못된 JSON
        
        def process(self):
            class MockContext:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
            return MockContext()
    
    message = BadJsonMessage()
    
    try:
        await on_bookmark_save(message)
        print("✅ JSON 오류 처리 성공 - 예외 없이 처리됨")
        return True
    except Exception as e:
        print(f"⚠️ JSON 오류 처리 중 예외: {e}")
        return False


async def main():
    """메인 테스트 함수"""
    
    print("🎯 Consumer 단독 테스트 시작!")
    print("=" * 60)
    
    # 테스트 시나리오 가져오기
    test_cases = get_test_scenarios()
    
    results = []
    
    # 개별 테스트 케이스들 실행
    for test_case in test_cases:
        result = await run_consumer_test_case(test_case)
        results.append((test_case['name'], result))
    
    # JSON 파싱 테스트
    json_result = await run_json_parsing_test()
    results.append(("JSON 파싱 오류", json_result))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} | {test_name}")
        if success:
            passed += 1
    
    print(f"\n📈 전체 결과: {passed}/{total} 테스트 통과")
    
    if passed == total:
        print("🎉 모든 Consumer 테스트가 성공했습니다!")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 로그를 확인해주세요.")
    
    return passed == total


if __name__ == "__main__":
    # 환경 변수 로드
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️ python-dotenv가 없습니다. 환경변수를 수동으로 설정해주세요.")
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 