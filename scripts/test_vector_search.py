#!/usr/bin/env python3
"""
북마크 벡터 검색 테스트 스크립트
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_async_session
from app.services.vector_service import VectorService
from loguru import logger

async def test_vector_search():
    """저장된 북마크들을 벡터 검색으로 찾아보는 테스트"""
    logger.info("🔍 벡터 검색 테스트 시작")
    
    try:
        # 벡터 서비스 초기화
        vector_service = VectorService()
        
        # 테스트 검색 쿼리들
        test_queries = [
            "인공지능과 머신러닝",
            "딥러닝 알고리즘",
            "AI 기술",
            "자연어처리",
            "데이터 학습",
            "전혀 관련없는 쿼리 - 요리 레시피"
        ]
        
        async for session in get_async_session():
            try:
                for i, query in enumerate(test_queries, 1):
                    logger.info(f"\n🔍 테스트 {i}: '{query}'")
                    logger.info("-" * 50)
                    
                    # 벡터 유사도 검색
                    results = await vector_service.similarity_search(
                        session=session,
                        query=query,
                        user_id=None,  # 모든 사용자의 북마크 검색
                        source_types=["bookmark_chunk"],
                        limit=5,
                        similarity_threshold=0.3  # 낮은 임계값으로 설정
                    )
                    
                    if results:
                        logger.info(f"✅ {len(results)}개의 유사한 북마크 발견:")
                        for j, (doc, score) in enumerate(results, 1):
                            logger.info(f"   {j}. 제목: {doc.title}")
                            logger.info(f"      사용자: {doc.user_id}")
                            logger.info(f"      유사도: {score:.4f}")
                            logger.info(f"      키워드: {doc.keywords}")
                            logger.info(f"      내용: {doc.content[:100]}...")
                            logger.info("")
                    else:
                        logger.warning("❌ 검색 결과가 없습니다.")
                    
                    # 특정 사용자로만 검색 (정수형 user_id 사용)
                    logger.info(f"🔍 사용자 456만 검색:")
                    user_results = await vector_service.similarity_search(
                        session=session,
                        query=query,
                        user_id=456,  # 정수형 user_id
                        source_types=["bookmark_chunk"],
                        limit=3,
                        similarity_threshold=0.3
                    )
                    
                    if user_results:
                        logger.info(f"✅ {len(user_results)}개의 결과:")
                        for j, (doc, score) in enumerate(user_results, 1):
                            logger.info(f"   {j}. {doc.title} (유사도: {score:.4f})")
                    else:
                        logger.info("   결과 없음")
                        
            except Exception as e:
                logger.error(f"❌ 검색 테스트 실패: {e}")
                raise
            finally:
                await session.close()
                
    except Exception as e:
        logger.error(f"❌ 벡터 검색 테스트 실패: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_vector_search()) 