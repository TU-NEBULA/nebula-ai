#!/usr/bin/env python3
"""
북마크 메트릭 테스트 스크립트
"""
import asyncio
import sys
import os

# 현재 경로를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.database import get_async_session
from app.repositories.bookmark_repository import BookmarkRepository

async def test_bookmark_metrics():
    """북마크 메트릭을 생성하기 위한 테스트"""
    print("북마크 메트릭 테스트 시작...")
    
    try:
        async for session in get_async_session():
            # 여러 사용자의 북마크 조회 (메트릭 생성)
            for user_id in range(1, 6):
                print(f"사용자 {user_id} 북마크 조회 중...")
                bookmarks = await BookmarkRepository.get_user_bookmarks(session, user_id, limit=10)
                print(f"사용자 {user_id}: {len(bookmarks)}개 북마크 발견")
                
                # 최근 북마크 조회
                recent_bookmarks = await BookmarkRepository.get_recent_bookmarks(session, user_id, days=30, limit=5)
                print(f"사용자 {user_id}: {len(recent_bookmarks)}개 최근 북마크 발견")
            
            # 분석용 북마크 조회
            print("분석용 북마크 조회 중...")
            analysis_bookmarks = await BookmarkRepository.get_bookmarks_for_analysis(session, [1, 2, 3, 4, 5], days=7)
            print(f"분석용 북마크: {len(analysis_bookmarks)}개 발견")
            
            print("북마크 메트릭 테스트 완료!")
            
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(test_bookmark_metrics()) 