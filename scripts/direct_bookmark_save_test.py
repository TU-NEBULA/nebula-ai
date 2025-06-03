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

async def direct_save_test():
    """북마크를 직접 데이터베이스에 저장합니다."""
    logger.info("🎯 북마크 직접 저장 테스트 시작")
    
    try:
        # 벡터 서비스 초기화
        vector_service = VectorService()
        
        # 테스트 텍스트
        test_content = """AI와 머신러닝은 현대 기술의 핵심입니다. 
인공지능은 데이터를 학습하여 패턴을 찾고 예측을 수행합니다.
딥러닝, 자연어처리, 컴퓨터 비전 등이 주요 분야입니다.
머신러닝 알고리즘에는 지도학습, 비지도학습, 강화학습이 있습니다.
신경망과 딥러닝은 복잡한 패턴을 학습할 수 있는 강력한 도구입니다."""
        
        # 테스트 데이터 구성
        test_data = {
            "user_id": "123",
            "source_id": "direct_test_bookmark_002", 
            "source_type": "bookmark_chunk",
            "title": "정수 유저ID 테스트 북마크",
            "url": "https://test.example.com/ai-ml-guide",
            "keywords": ["AI", "머신러닝", "딥러닝", "테스트"],
            "summary": "AI와 머신러닝에 대한 기본 설명",
            "extra_metadata": {
                "test_type": "direct_save",
                "created_by": "direct_bookmark_save_test.py",
                "original_user_id": 123
            }
        }
        
        logger.info("💾 VectorService를 통한 북마크 저장 시작...")
        
        # 데이터베이스 세션을 사용하여 저장
        async for session in get_async_session():
            try:
                # VectorService의 save_document 메서드 사용
                saved_vectors = await vector_service.save_document(
                    session=session,
                    user_id=test_data["user_id"],
                    source_id=test_data["source_id"],
                    source_type=test_data["source_type"],
                    content=test_content,
                    title=test_data["title"],
                    url=test_data["url"],
                    keywords=test_data["keywords"],
                    summary=test_data["summary"],
                    extra_metadata=test_data["extra_metadata"]
                )
                
                if saved_vectors:
                    logger.info(f"✅ 벡터 서비스를 통한 저장 성공! ({len(saved_vectors)}개 청크)")
                    logger.info(f"   👤 사용자: {test_data['user_id']}")
                    logger.info(f"   🆔 소스: {test_data['source_id']}")
                    logger.info(f"   📝 제목: {test_data['title']}")
                    logger.info(f"   🔗 URL: {test_data['url']}")
                    logger.info(f"   🏷️ 키워드: {test_data['keywords']}")
                    
                    # 각 저장된 벡터 정보 출력
                    for i, vector in enumerate(saved_vectors):
                        logger.info(f"   📄 청크 {i+1}: {vector.chunk_index} (ID: {vector.id})")
                    
                    # 저장 확인
                    from sqlalchemy import text
                    result = await session.execute(text("SELECT COUNT(*) FROM document_vectors WHERE user_id = '123'"))
                    count = result.scalar()
                    logger.info(f"📊 user_id='123'의 북마크 개수: {count}개")
                    
                    if count > 0:
                        logger.info("🎉 북마크 저장 테스트 성공!")
                        
                        # 상세 조회
                        result = await session.execute(text("""
                            SELECT 
                                source_id, 
                                source_type,
                                chunk_index,
                                title, 
                                LEFT(content, 80) as content_preview,
                                keywords,
                                created_at
                            FROM document_vectors 
                            WHERE user_id = '123'
                            ORDER BY created_at DESC, chunk_index ASC
                        """))
                        
                        rows = result.fetchall()
                        logger.info(f"📋 저장된 북마크 목록 ({len(rows)}개):")
                        for i, row in enumerate(rows, 1):
                            logger.info(f"   {i}. {row.source_id} 청크#{row.chunk_index} ({row.source_type})")
                            logger.info(f"      제목: {row.title}")
                            logger.info(f"      내용: {row.content_preview}...")
                            logger.info(f"      키워드: {row.keywords}")
                            logger.info(f"      생성: {row.created_at}")
                            logger.info("      " + "-"*50)
                    else:
                        logger.error("❌ 북마크가 저장되지 않았습니다!")
                else:
                    logger.error("❌ 벡터 서비스 저장 실패!")
                    
            except Exception as e:
                logger.error(f"❌ 저장 실패: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()
                    
    except Exception as e:
        logger.error(f"❌ 직접 저장 테스트 실패: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(direct_save_test()) 