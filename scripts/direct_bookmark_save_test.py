#!/usr/bin/env python3
"""
북마크 직접 저장 테스트 스크립트
"""
import asyncio
import sys
import os
from datetime import datetime
import uuid

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_async_session
from app.models.chat import DocumentVector
from app.services.vector_service import VectorService
from loguru import logger

async def test_direct_bookmark_save():
    """북마크를 직접 저장하는 테스트"""
    logger.info("📝 북마크 직접 저장 테스트 시작")
    
    try:
        # 벡터 서비스 초기화
        vector_service = VectorService()
        
        # 테스트용 북마크 데이터
        test_bookmark = {
            "title": "인공지능과 머신러닝 완벽 가이드",
            "url": "https://example.com/ai-ml-guide",
            "content": """
            인공지능(AI)과 머신러닝(ML)은 현대 기술의 핵심입니다. 
            딥러닝, 신경망, 자연어처리, 컴퓨터 비전 등 다양한 분야에서 
            혁신적인 발전을 이루고 있습니다. 데이터 사이언스와 빅데이터 
            분석을 통해 패턴을 학습하고 예측 모델을 구축할 수 있습니다.
            파이썬, TensorFlow, PyTorch 등의 도구들이 널리 사용됩니다.
            """,
            "keywords": ["인공지능", "머신러닝", "딥러닝", "데이터사이언스", "파이썬"],
            "summary": "AI와 ML 기술의 전반적인 개요와 활용 분야 소개"
        }
        
        # 정수형 user_id 사용 (문자열 변환 없이)
        user_id = 456  # 직접 정수 사용
        source_id = "direct_test_bookmark_003"
        
        async for session in get_async_session():
            try:
                logger.info(f"📊 사용자 ID: {user_id} (타입: {type(user_id).__name__})")
                logger.info(f"📋 북마크 ID: {source_id}")
                logger.info(f"📝 제목: {test_bookmark['title']}")
                
                # VectorService를 사용해서 저장
                saved_vectors = await vector_service.save_document(
                    session=session,
                    user_id=user_id,  # 정수 직접 전달
                    source_id=source_id,
                    source_type="bookmark_chunk",
                    content=test_bookmark["content"],
                    title=test_bookmark["title"],
                    url=test_bookmark["url"],
                    keywords=test_bookmark["keywords"],
                    summary=test_bookmark["summary"],
                    extra_metadata={
                        "test_type": "direct_save",
                        "category": "technology"
                    }
                )
                
                if saved_vectors:
                    logger.info(f"✅ 저장 성공!")
                    logger.info(f"📄 저장된 청크 수: {len(saved_vectors)}")
                    
                    # 첫 번째 벡터 정보 출력
                    first_vector = saved_vectors[0]
                    logger.info(f"🔍 첫 번째 벡터 정보:")
                    logger.info(f"   ID: {first_vector.id}")
                    logger.info(f"   사용자 ID: {first_vector.user_id} (타입: {type(first_vector.user_id).__name__})")
                    logger.info(f"   소스 ID: {first_vector.source_id}")
                    logger.info(f"   제목: {first_vector.title}")
                    
                    # 임베딩 차원 확인 (배열 처리 개선)
                    embedding_dim = 0
                    try:
                        if first_vector.embedding is not None:
                            embedding_dim = len(first_vector.embedding)
                    except Exception:
                        embedding_dim = "확인불가"
                    
                    logger.info(f"   임베딩 차원: {embedding_dim}")
                    logger.info(f"   키워드: {first_vector.keywords}")
                else:
                    logger.error("❌ 저장 실패 - 반환된 벡터가 없습니다.")
                
            except Exception as e:
                logger.error(f"❌ 저장 과정에서 오류 발생: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()
                
    except Exception as e:
        logger.error(f"❌ 북마크 저장 테스트 실패: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_direct_bookmark_save()) 