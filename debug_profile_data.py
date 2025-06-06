#!/usr/bin/env python3
"""
사용자 프로필 데이터 확인 스크립트

북마크 저장 후 실제로 저장된 프로필 데이터를 확인합니다.
"""

import asyncio
import sys
import os
from datetime import datetime

# 현재 디렉토리를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import select
from loguru import logger

from app.core.database import get_async_session
from app.models.user_profile import UserProfile
from app.models.chat import UserProfile as ChatUserProfile
from app.repositories.user_profile_repository import UserProfileRepository


async def check_user_profile_data(user_id: int):
    """특정 사용자의 프로필 데이터를 상세히 확인"""
    logger.info(f"🔍 사용자 {user_id}의 프로필 데이터 확인 시작")
    
    async for session in get_async_session():
        try:
            # 1. user_profiles 테이블에서 프로필 조회
            stmt = select(UserProfile).where(UserProfile.user_id == user_id)
            result = await session.execute(stmt)
            main_profile = result.scalar_one_or_none()
            
            print("\n=== MAIN USER PROFILE (user_profiles) ===")
            if main_profile:
                print(f"✅ 프로필 존재: ID {main_profile.id}")
                print(f"👤 사용자 ID: {main_profile.user_id}")
                print(f"📅 생성일: {main_profile.created_at}")
                print(f"🔄 업데이트일: {main_profile.updated_at}")
                try:
                    if main_profile.profile_vector is not None:
                        if hasattr(main_profile.profile_vector, '__len__'):
                            print(f"🎯 프로필 벡터: {len(main_profile.profile_vector)}차원")
                        else:
                            print(f"🎯 프로필 벡터: 형식 오류 (타입: {type(main_profile.profile_vector)})")
                    else:
                        print(f"🎯 프로필 벡터: 0차원")
                except Exception as e:
                    print(f"🎯 프로필 벡터: 처리 오류 - {e}")
                print(f"💪 벡터 강도: {main_profile.vector_strength}")
                print(f"📊 완성도 점수: {main_profile.completeness_score}")
                print(f"📚 총 북마크: {main_profile.total_bookmarks}")
                
                # 벡터 상세 정보
                print("🔢 벡터 분석:")
                try:
                    if main_profile.profile_vector is None:
                        print("   ❌ 벡터가 None입니다")
                    else:
                        print(f"   📊 벡터 타입: {type(main_profile.profile_vector)}")
                        
                        # 안전한 길이 체크
                        try:
                            vector_len = len(main_profile.profile_vector)
                            print(f"   📏 벡터 길이: {vector_len}")
                            
                            if vector_len > 0:
                                # 첫 번째 요소 체크
                                first_elem = main_profile.profile_vector[0]
                                print(f"   🎯 첫 번째 요소: {first_elem} (타입: {type(first_elem)})")
                                
                                # 모든 요소가 0인지 체크
                                try:
                                    import numpy as np
                                    vector_array = np.array(main_profile.profile_vector, dtype=float)
                                    non_zero_count = np.count_nonzero(vector_array)
                                    vector_sum = np.sum(np.abs(vector_array))
                                    print(f"   ✅ 0이 아닌 값 개수: {non_zero_count}")
                                    print(f"   📊 절대값 합계: {vector_sum:.6f}")
                                    
                                    if vector_sum > 0:
                                        print(f"   ✅ 벡터에 실제 값이 있습니다!")
                                    else:
                                        print(f"   ❌ 모든 벡터 값이 0입니다")
                                except Exception as numpy_error:
                                    print(f"   ⚠️ NumPy 분석 실패: {numpy_error}")
                                    # 수동으로 체크
                                    try:
                                        manual_check = any(float(x) != 0.0 for x in main_profile.profile_vector[:100])  # 처음 100개만 체크
                                        print(f"   🔍 수동 체크 (처음 100개): {'값 있음' if manual_check else '모두 0'}")
                                    except Exception as manual_error:
                                        print(f"   ❌ 수동 체크도 실패: {manual_error}")
                            
                        except Exception as len_error:
                            print(f"   ❌ 길이 체크 실패: {len_error}")
                            
                except Exception as e:
                    print(f"   ❌ 벡터 분석 전체 실패: {e}")
                
                # 키워드 빈도
                print(f"🔤 키워드 빈도: {main_profile.keywords_frequency}")
                print(f"📂 카테고리 분포: {main_profile.categories_distribution}")
                print(f"⚙️ 설정: {main_profile.preferences}")
                
            else:
                print("❌ 메인 프로필이 존재하지 않음")
            
            # 2. chat_user_profiles 테이블에서 프로필 조회 (있다면)
            try:
                chat_stmt = select(ChatUserProfile).where(ChatUserProfile.user_id == user_id)
                chat_result = await session.execute(chat_stmt)
                chat_profile = chat_result.scalar_one_or_none()
                
                print("\n=== CHAT USER PROFILE (chat_user_profiles) ===")
                if chat_profile:
                    print(f"✅ 채팅 프로필 존재")
                    print(f"👤 사용자 ID: {chat_profile.user_id}")
                    print(f"📝 표시명: {chat_profile.display_name}")
                    print(f"⚙️ 설정: {chat_profile.preferences}")
                    print(f"📊 채팅 통계: {chat_profile.chat_statistics}")
                    print(f"📅 생성일: {chat_profile.created_at}")
                    print(f"🔄 업데이트일: {chat_profile.updated_at}")
                else:
                    print("❌ 채팅 프로필이 존재하지 않음")
            except Exception as e:
                print(f"⚠️ 채팅 프로필 조회 중 오류: {e}")
            
            # 3. Repository를 통한 조회
            print("\n=== REPOSITORY 조회 ===")
            try:
                user_profile_repo = UserProfileRepository()
                repo_profile = await user_profile_repo.get_or_create_profile(session, user_id)
                print(f"✅ Repository로 조회 성공")
                print(f"👤 사용자 ID: {repo_profile.user_id}")
                print(f"🆔 프로필 ID: {repo_profile.id}")
                print(f"💪 벡터 강도: {repo_profile.vector_strength}")
                print(f"📊 완성도: {repo_profile.completeness_score}")
            except Exception as e:
                print(f"❌ Repository 조회 실패: {e}")
            
        except Exception as e:
            logger.error(f"❌ 프로필 데이터 확인 실패: {e}")
            print(f"❌ 오류 발생: {e}")
        
        break  # async for는 한 번만 실행


async def check_all_profiles():
    """모든 사용자 프로필 개요 확인"""
    logger.info("📋 모든 사용자 프로필 개요 확인")
    
    async for session in get_async_session():
        try:
            stmt = select(UserProfile)
            result = await session.execute(stmt)
            all_profiles = result.scalars().all()
            
            print(f"\n=== 전체 프로필 개요 ===")
            print(f"📊 총 프로필 수: {len(all_profiles)}")
            
            if all_profiles:
                print("\n📋 프로필 목록:")
                for profile in all_profiles:
                    try:
                        vector_info = "벡터 없음"
                        if profile.profile_vector is not None:
                            if hasattr(profile.profile_vector, '__len__'):
                                vector_info = f"벡터 있음 ({len(profile.profile_vector)}차원)" if len(profile.profile_vector) > 0 else "벡터 없음"
                            else:
                                vector_info = "벡터 데이터 형식 오류"
                        
                        vector_strength = profile.vector_strength if profile.vector_strength else 0.0
                        updated = profile.updated_at.strftime("%Y-%m-%d %H:%M") if profile.updated_at else "업데이트 없음"
                        
                        print(f"  👤 사용자 {profile.user_id}: {vector_info} (강도: {vector_strength:.3f}) - {updated}")
                    except Exception as e:
                        print(f"  ❌ 사용자 {profile.user_id}: 프로필 처리 오류 - {e}")
            
        except Exception as e:
            logger.error(f"❌ 전체 프로필 조회 실패: {e}")
            print(f"❌ 오류 발생: {e}")
        
        break


async def main():
    """메인 함수"""
    print("🔍 사용자 프로필 데이터 확인 도구")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
            await check_user_profile_data(user_id)
        except ValueError:
            print("❌ 올바른 사용자 ID를 입력해주세요 (숫자)")
    else:
        await check_all_profiles()
        
        # 특정 사용자 ID 입력 받기
        print("\n" + "=" * 50)
        user_input = input("📝 확인할 사용자 ID를 입력하세요 (Enter로 종료): ").strip()
        
        if user_input:
            try:
                user_id = int(user_input)
                await check_user_profile_data(user_id)
            except ValueError:
                print("❌ 올바른 사용자 ID를 입력해주세요")


if __name__ == "__main__":
    asyncio.run(main()) 