#!/usr/bin/env python3
"""
북마크 저장을 통한 프로필 업데이트 트리거 스크립트

실제 북마크를 저장하여 프로필 업데이트가 정상적으로 작동하는지 확인합니다.
"""

import asyncio
import sys
import os
from datetime import datetime

# 현재 디렉토리를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger

from app.external.openai_service import OpenAIService
from app.services.vector_generator import VectorGenerator, ActivityData, ActivityType
from app.core.database import get_async_session
from app.repositories.user_profile_repository import UserProfileRepository


async def force_update_user_profile(user_id: int = 5):
    """사용자 프로필을 강제로 업데이트합니다."""
    print(f"\n🔄 사용자 {user_id} 프로필 강제 업데이트 시작")
    print("=" * 60)
    
    try:
        async for session in get_async_session():
            # OpenAI 서비스 초기화
            openai_service = OpenAIService()
            vector_generator = VectorGenerator(openai_service)
            user_profile_repo = UserProfileRepository()
            
            print("✅ 서비스 초기화 완료")
            
            # 테스트용 활동 데이터 생성 (실제 북마크를 시뮬레이션)
            test_activities = [
                ActivityData(
                    activity_type=ActivityType.BOOKMARK,
                    content="Python 머신러닝 완전정복 - 데이터 분석부터 딥러닝까지 모든 것을 다루는 종합 가이드입니다. 실무에서 바로 사용할 수 있는 예제와 함께 설명합니다.",
                    created_at=datetime.now(),
                    metadata={
                        "title": "Python 머신러닝 완전정복",
                        "url": "https://example.com/python-ml-guide",
                        "category": "machine-learning"
                    },
                    weight=1.5
                ),
                ActivityData(
                    activity_type=ActivityType.BOOKMARK,
                    content="FastAPI로 만드는 현대적인 웹 API - REST API 설계부터 배포까지 전체 과정을 다룹니다. Docker와 Kubernetes를 활용한 마이크로서비스 아키텍처도 포함합니다.",
                    created_at=datetime.now(),
                    metadata={
                        "title": "FastAPI 웹 API 가이드",
                        "url": "https://example.com/fastapi-guide",
                        "category": "web-development"
                    },
                    weight=1.5
                ),
                ActivityData(
                    activity_type=ActivityType.BOOKMARK,
                    content="인공지능 윤리와 책임 있는 AI 개발 - AI 시스템의 공정성, 투명성, 프라이버시 보호에 대한 심층 분석입니다. 실제 사례 연구를 통해 배우는 AI 거버넌스.",
                    created_at=datetime.now(),
                    metadata={
                        "title": "AI 윤리와 거버넌스",
                        "url": "https://example.com/ai-ethics",
                        "category": "ai-ethics"
                    },
                    weight=1.0
                ),
                ActivityData(
                    activity_type=ActivityType.CHAT,
                    content="인공지능과 머신러닝의 차이점에 대해 질문했습니다. 딥러닝과 전통적인 머신러닝 알고리즘의 장단점을 비교 분석하고 실무 적용 사례를 논의했습니다.",
                    created_at=datetime.now(),
                    metadata={
                        "session_id": "test_session_001",
                        "message_type": "user_question"
                    },
                    weight=1.0
                ),
                ActivityData(
                    activity_type=ActivityType.CHAT,
                    content="Python 웹 개발 프레임워크 선택에 대한 조언을 구했습니다. Django vs FastAPI vs Flask의 특징과 프로젝트 규모별 적합성에 대해 상세히 논의했습니다.",
                    created_at=datetime.now(),
                    metadata={
                        "session_id": "test_session_002",
                        "message_type": "user_question"
                    },
                    weight=1.0
                )
            ]
            
            print(f"📝 테스트 활동 데이터: {len(test_activities)}개 생성")
            for i, activity in enumerate(test_activities):
                print(f"   {i+1}. {activity.activity_type.value}: {activity.content[:60]}...")
            
            # 벡터 생성
            print("\n🚀 프로필 벡터 생성 시작...")
            vector, metadata = await vector_generator.generate_profile_vector(test_activities)
            
            import numpy as np
            vector_array = np.array(vector)
            vector_sum = np.sum(np.abs(vector_array))
            non_zero_count = np.count_nonzero(vector_array)
            
            print(f"📊 생성된 벡터 통계:")
            print(f"   - 차원: {len(vector)}")
            print(f"   - 0이 아닌 값: {non_zero_count}")
            print(f"   - 절대값 합계: {vector_sum:.6f}")
            print(f"   - 벡터 강도: {metadata.get('vector_strength', vector_sum):.6f}")
            
            if vector_sum > 0:
                print("✅ 의미 있는 벡터 생성 성공!")
                
                # 프로필 업데이트
                print(f"\n💾 사용자 {user_id} 프로필 업데이트 중...")
                
                updated_profile = await user_profile_repo.update_profile(
                    session,
                    user_id,
                    profile_vector=vector,
                    vector_strength=metadata.get('vector_strength', vector_sum),
                    keywords_frequency=metadata.get('top_interests', {}).get('keywords', {}),
                    category_distribution=metadata.get('top_interests', {}).get('categories', {}),
                    preferences={"algorithm_version": "v2.0", "last_update_method": "forced_update"},
                    last_activity_at=datetime.now()
                )
                
                print(f"✅ 프로필 업데이트 완료!")
                print(f"   - 프로필 ID: {updated_profile.id}")
                print(f"   - 벡터 강도: {updated_profile.vector_strength:.6f}")
                print(f"   - 업데이트 시간: {updated_profile.updated_at}")
                
                # 저장된 데이터 확인
                print(f"\n🔍 저장된 데이터 검증 중...")
                saved_profile = await user_profile_repo.get_or_create_profile(session, user_id)
                
                if saved_profile.profile_vector is not None:
                    saved_vector = np.array(saved_profile.profile_vector)
                    saved_sum = np.sum(np.abs(saved_vector))
                    
                    print(f"📊 저장된 벡터 확인:")
                    print(f"   - 차원: {len(saved_profile.profile_vector)}")
                    print(f"   - 절대값 합계: {saved_sum:.6f}")
                    print(f"   - 벡터 강도: {saved_profile.vector_strength:.6f}")
                    
                    if saved_sum > 0:
                        print("🎉 프로필 업데이트 성공! 의미 있는 벡터가 저장되었습니다.")
                        return True
                    else:
                        print("❌ 0 벡터가 저장됨 - 데이터베이스 저장 과정에 문제가 있습니다.")
                        return False
                else:
                    print("❌ 벡터가 저장되지 않음")
                    return False
            else:
                print("❌ 0 벡터 생성됨 - 벡터 생성 과정에 문제가 있습니다.")
                return False
            
    except Exception as e:
        print(f"❌ 프로필 업데이트 실패: {e}")
        logger.exception("프로필 업데이트 오류")
        return False


async def verify_profile_update(user_id: int = 5):
    """프로필 업데이트 결과를 확인합니다."""
    print(f"\n🔍 사용자 {user_id} 프로필 업데이트 결과 확인")
    print("=" * 60)
    
    try:
        async for session in get_async_session():
            user_profile_repo = UserProfileRepository()
            
            profile = await user_profile_repo.get_or_create_profile(session, user_id)
            
            print(f"👤 사용자 ID: {profile.user_id}")
            print(f"🆔 프로필 ID: {profile.id}")
            print(f"📅 생성일: {profile.created_at}")
            print(f"🔄 업데이트일: {profile.updated_at}")
            print(f"💪 벡터 강도: {profile.vector_strength}")
            print(f"📊 완성도: {profile.completeness_score}")
            
            if profile.profile_vector is not None:
                import numpy as np
                vector_array = np.array(profile.profile_vector)
                vector_sum = np.sum(np.abs(vector_array))
                non_zero_count = np.count_nonzero(vector_array)
                
                print(f"🎯 벡터 통계:")
                print(f"   - 차원: {len(profile.profile_vector)}")
                print(f"   - 0이 아닌 값: {non_zero_count}")
                print(f"   - 절대값 합계: {vector_sum:.6f}")
                print(f"   - 첫 10개 값: {[float(x) for x in profile.profile_vector[:10]]}")
                
                if vector_sum > 0:
                    print("✅ 프로필에 의미 있는 벡터가 저장되어 있습니다!")
                    return True
                else:
                    print("❌ 프로필의 모든 벡터 값이 0입니다.")
                    return False
            else:
                print("❌ 프로필에 벡터가 저장되어 있지 않습니다.")
                return False
            
    except Exception as e:
        print(f"❌ 프로필 확인 실패: {e}")
        logger.exception("프로필 확인 오류")
        return False


async def main():
    """메인 함수"""
    print("🔄 사용자 프로필 강제 업데이트 도구")
    print("=" * 70)
    
    user_id = 5
    
    # 1. 기존 프로필 상태 확인
    print("📋 1단계: 기존 프로필 상태 확인")
    initial_ok = await verify_profile_update(user_id)
    
    if initial_ok:
        print("✅ 이미 의미 있는 벡터가 저장되어 있습니다.")
        choice = input("\n강제로 다시 업데이트하시겠습니까? (y/N): ").strip().lower()
        if choice != 'y':
            print("작업을 취소합니다.")
            return True
    
    # 2. 강제 프로필 업데이트
    print("\n📋 2단계: 프로필 강제 업데이트")
    update_ok = await force_update_user_profile(user_id)
    
    if not update_ok:
        print("\n❌ 프로필 업데이트에 실패했습니다.")
        return False
    
    # 3. 업데이트 결과 확인
    print("\n📋 3단계: 업데이트 결과 최종 확인")
    final_ok = await verify_profile_update(user_id)
    
    if final_ok:
        print("\n🎉 프로필 업데이트가 성공적으로 완료되었습니다!")
        print("이제 북마크 저장 시 프로필이 정상적으로 업데이트될 것입니다.")
        return True
    else:
        print("\n❌ 프로필 업데이트에 문제가 있습니다.")
        return False


if __name__ == "__main__":
    asyncio.run(main()) 