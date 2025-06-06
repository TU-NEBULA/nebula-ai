#!/usr/bin/env python3
"""
벡터 생성 과정 테스트 및 디버깅 스크립트

실제 벡터 생성 과정에서 어느 단계에서 문제가 발생하는지 확인합니다.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# 현재 디렉토리를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger

from app.external.openai_service import OpenAIService
from app.services.vector_generator import VectorGenerator, ActivityData, ActivityType
from app.core.database import get_async_session
from app.repositories.user_profile_repository import UserProfileRepository


async def test_openai_service():
    """OpenAI 서비스가 정상 작동하는지 테스트"""
    print("\n🔧 1. OpenAI 서비스 테스트")
    print("=" * 50)
    
    try:
        openai_service = OpenAIService()
        print("✅ OpenAI 서비스 초기화 성공")
        
        # 간단한 임베딩 테스트
        test_text = "인공지능과 머신러닝에 대한 테스트"
        print(f"📝 테스트 텍스트: {test_text}")
        
        embedding_response = await openai_service.create_embedding(
            text=test_text,
            model="text-embedding-3-small"
        )
        
        if embedding_response and hasattr(embedding_response, 'data') and embedding_response.data:
            embedding = embedding_response.data[0].embedding
            print(f"✅ 임베딩 생성 성공 - 차원: {len(embedding)}")
            print(f"📊 임베딩 첫 5개 값: {embedding[:5]}")
            print(f"📊 절대값 합계: {sum(abs(x) for x in embedding):.6f}")
            
            if sum(abs(x) for x in embedding) > 0:
                print("✅ 의미 있는 벡터 생성됨")
                return True
            else:
                print("❌ 모든 값이 0인 벡터 생성됨")
                return False
        else:
            print("❌ 임베딩 응답이 비어있음")
            return False
            
    except Exception as e:
        print(f"❌ OpenAI 서비스 테스트 실패: {e}")
        return False


async def test_vector_generator():
    """VectorGenerator가 정상 작동하는지 테스트"""
    print("\n🔧 2. VectorGenerator 테스트")
    print("=" * 50)
    
    try:
        openai_service = OpenAIService()
        vector_generator = VectorGenerator(openai_service)
        print("✅ VectorGenerator 초기화 성공")
        
        # 테스트용 활동 데이터 생성
        test_activities = [
            ActivityData(
                activity_type=ActivityType.BOOKMARK,
                content="Python 프로그래밍 기초 - 객체지향 프로그래밍과 웹 개발에 대한 내용입니다.",
                created_at=datetime.now(),
                metadata={
                    "title": "Python 프로그래밍 기초",
                    "url": "https://example.com/python-basics",
                    "category": "programming"
                },
                weight=1.5
            ),
            ActivityData(
                activity_type=ActivityType.CHAT,
                content="인공지능 머신러닝에 대해 질문하고 답변을 받았습니다.",
                created_at=datetime.now(),
                metadata={
                    "session_id": "test_session",
                    "role": "user"
                },
                weight=1.0
            )
        ]
        
        print(f"📝 테스트 활동 데이터: {len(test_activities)}개")
        for i, activity in enumerate(test_activities):
            print(f"   {i+1}. {activity.activity_type.value}: {activity.content[:50]}...")
        
        # 벡터 생성 테스트
        print("\n🚀 벡터 생성 시작...")
        vector, metadata = await vector_generator.generate_profile_vector(
            activities=test_activities
        )
        
        print(f"✅ 벡터 생성 완료 - 차원: {len(vector)}")
        print(f"📊 메타데이터: {list(metadata.keys())}")
        
        if vector and len(vector) > 0:
            import numpy as np
            vector_array = np.array(vector)
            non_zero_count = np.count_nonzero(vector_array)
            vector_sum = np.sum(np.abs(vector_array))
            
            print(f"📊 벡터 통계:")
            print(f"   - 전체 차원: {len(vector)}")
            print(f"   - 0이 아닌 값: {non_zero_count}")
            print(f"   - 절대값 합계: {vector_sum:.6f}")
            print(f"   - 첫 10개 값: {[float(x) for x in vector[:10]]}")
            
            if vector_sum > 0:
                print("✅ 의미 있는 벡터 생성됨")
                return True, vector, metadata
            else:
                print("❌ 모든 값이 0인 벡터 생성됨")
                return False, vector, metadata
        else:
            print("❌ 빈 벡터 생성됨")
            return False, [], {}
            
    except Exception as e:
        print(f"❌ VectorGenerator 테스트 실패: {e}")
        logger.exception("VectorGenerator 테스트 오류")
        return False, [], {}


async def test_database_save(test_vector, test_metadata):
    """데이터베이스 저장 테스트"""
    print("\n🔧 3. 데이터베이스 저장 테스트")
    print("=" * 50)
    
    test_user_id = 999  # 테스트용 사용자 ID
    
    try:
        async for session in get_async_session():
            user_profile_repo = UserProfileRepository()
            
            # 기존 테스트 프로필 삭제 (있다면)
            from sqlmodel import select, delete
            from app.models.user_profile import UserProfile
            
            existing_stmt = select(UserProfile).where(UserProfile.user_id == test_user_id)
            existing_result = await session.execute(existing_stmt)
            existing_profile = existing_result.scalar_one_or_none()
            
            if existing_profile:
                await session.delete(existing_profile)
                await session.commit()
                print(f"🗑️ 기존 테스트 프로필 삭제됨")
            
            # 새 프로필 생성
            print(f"📝 테스트 사용자 {test_user_id} 프로필 생성...")
            
            profile = await user_profile_repo.update_profile(
                session,
                test_user_id,
                profile_vector=test_vector,
                vector_strength=test_metadata.get('vector_strength', 0.5),
                keywords_frequency={"test": {"frequency": 1, "weight": 0.5}},
                preferences={"test_mode": True}
            )
            
            print(f"✅ 프로필 저장 성공 - ID: {profile.id}")
            
            # 저장된 데이터 다시 조회
            saved_profile = await user_profile_repo.get_or_create_profile(session, test_user_id)
            
            if saved_profile.profile_vector:
                import numpy as np
                saved_vector = np.array(saved_profile.profile_vector)
                saved_sum = np.sum(np.abs(saved_vector))
                
                print(f"📊 저장된 벡터 통계:")
                print(f"   - 차원: {len(saved_profile.profile_vector)}")
                print(f"   - 절대값 합계: {saved_sum:.6f}")
                print(f"   - 벡터 강도: {saved_profile.vector_strength}")
                
                if saved_sum > 0:
                    print("✅ 데이터베이스에 올바르게 저장됨")
                    return True
                else:
                    print("❌ 데이터베이스에 0 벡터로 저장됨")
                    return False
            else:
                print("❌ 벡터가 저장되지 않음")
                return False
            
    except Exception as e:
        print(f"❌ 데이터베이스 저장 테스트 실패: {e}")
        logger.exception("데이터베이스 저장 테스트 오류")
        return False


async def test_user_profile_update(user_id: int = 5):
    """실제 사용자 프로필 업데이트 과정 테스트"""
    print(f"\n🔧 4. 사용자 {user_id} 프로필 업데이트 테스트")
    print("=" * 50)
    
    try:
        async for session in get_async_session():
            # 실제 북마크 데이터 확인
            from sqlmodel import select
            from app.models.bookmark import BookmarkAIStatus
            
            bookmark_stmt = select(BookmarkAIStatus).where(BookmarkAIStatus.user_id == user_id).limit(5)
            bookmark_result = await session.execute(bookmark_stmt)
            bookmarks = list(bookmark_result.scalars().all())
            
            print(f"📚 사용자 {user_id}의 북마크: {len(bookmarks)}개")
            
            if bookmarks:
                for i, bookmark in enumerate(bookmarks[:3]):  # 처음 3개만 출력
                    print(f"   {i+1}. {bookmark.title[:50]}...")
                    if hasattr(bookmark, 'summary') and bookmark.summary:
                        print(f"      요약: {bookmark.summary[:100]}...")
            
            # 실제 프로필 업데이트 과정 시뮬레이션
            openai_service = OpenAIService()
            vector_generator = VectorGenerator(openai_service)
            
            # 북마크 데이터를 ActivityData로 변환
            activities = []
            for bookmark in bookmarks:
                content_parts = []
                if bookmark.title:
                    content_parts.append(bookmark.title)
                if hasattr(bookmark, 'summary') and bookmark.summary:
                    content_parts.append(bookmark.summary)
                
                if content_parts:
                    activities.append(ActivityData(
                        activity_type=ActivityType.BOOKMARK,
                        content=" ".join(content_parts),
                        created_at=bookmark.created_at,
                        metadata={
                            "url": getattr(bookmark, 'url', ''),
                            "category": getattr(bookmark, 'category', 'general'),
                            "source": "bookmark_data"
                        },
                        weight=1.5
                    ))
            
            if activities:
                print(f"🚀 {len(activities)}개 활동으로 벡터 생성 시작...")
                
                vector, metadata = await vector_generator.generate_profile_vector(activities)
                
                import numpy as np
                vector_array = np.array(vector)
                vector_sum = np.sum(np.abs(vector_array))
                
                print(f"📊 생성된 벡터:")
                print(f"   - 차원: {len(vector)}")
                print(f"   - 절대값 합계: {vector_sum:.6f}")
                print(f"   - 메타데이터: {list(metadata.keys())}")
                
                if vector_sum > 0:
                    print("✅ 의미 있는 벡터 생성됨")
                    
                    # 실제 저장
                    user_profile_repo = UserProfileRepository()
                    updated_profile = await user_profile_repo.update_profile(
                        session,
                        user_id,
                        profile_vector=vector,
                        vector_strength=metadata.get('vector_strength', vector_sum),
                        last_activity_at=datetime.now()
                    )
                    
                    print(f"✅ 프로필 업데이트 완료 - 벡터 강도: {updated_profile.vector_strength:.6f}")
                    return True
                else:
                    print("❌ 0 벡터 생성됨")
                    return False
            else:
                print("❌ 활동 데이터가 없음")
                return False
            
    except Exception as e:
        print(f"❌ 사용자 프로필 업데이트 테스트 실패: {e}")
        logger.exception("사용자 프로필 업데이트 테스트 오류")
        return False


async def main():
    """메인 테스트 함수"""
    print("🧪 벡터 생성 과정 종합 테스트")
    print("=" * 60)
    
    results = []
    
    # 1. OpenAI 서비스 테스트
    openai_ok = await test_openai_service()
    results.append(("OpenAI 서비스", openai_ok))
    
    if not openai_ok:
        print("\n❌ OpenAI 서비스에 문제가 있어 테스트를 중단합니다.")
        return False
    
    # 2. VectorGenerator 테스트
    vector_ok, test_vector, test_metadata = await test_vector_generator()
    results.append(("VectorGenerator", vector_ok))
    
    if not vector_ok:
        print("\n❌ VectorGenerator에 문제가 있어 일부 테스트를 건너뜁니다.")
    else:
        # 3. 데이터베이스 저장 테스트
        db_ok = await test_database_save(test_vector, test_metadata)
        results.append(("데이터베이스 저장", db_ok))
    
    # 4. 실제 사용자 프로필 업데이트 테스트
    profile_ok = await test_user_profile_update()
    results.append(("사용자 프로필 업데이트", profile_ok))
    
    # 결과 요약
    print("\n📋 테스트 결과 요약")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 모든 테스트 통과!")
    else:
        print("\n⚠️ 일부 테스트 실패 - 로그를 확인해주세요.")
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(main()) 