#!/usr/bin/env python3
"""
실제 HTML 파일을 사용한 북마크 저장 테스트
"""
import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_async_session
from app.services.vector_service import VectorService
from tests.manual.data_helper import TestDataHelper
from loguru import logger

async def test_html_bookmarks():
    """실제 HTML 파일들을 사용해서 북마크를 저장하고 검색하는 테스트"""
    logger.info("📁 HTML 파일 북마크 테스트 시작")
    
    try:
        # 데이터 헬퍼와 벡터 서비스 초기화
        data_helper = TestDataHelper()
        vector_service = VectorService()
        
        # 사용 가능한 HTML 파일들 확인
        html_files = data_helper.get_html_files()
        logger.info(f"📋 사용 가능한 HTML 파일: {len(html_files)}개")
        for file in html_files:
            logger.info(f"   📄 {file}")
        
        # 각 HTML 파일을 북마크로 저장
        user_id = 789  # 정수형 user_id 사용
        saved_bookmarks = []
        
        async for session in get_async_session():
            try:
                for i, html_file in enumerate(html_files):
                    logger.info(f"\n📝 {i+1}. HTML 파일 처리: {html_file}")
                    
                    # HTML 파일 읽기
                    html_path = Path(data_helper.data_dir) / "html" / html_file
                    with open(html_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    # HTML에서 텍스트 추출 (간단한 태그 제거)
                    import re
                    text_content = re.sub(r'<[^>]+>', ' ', html_content)
                    text_content = ' '.join(text_content.split())  # 공백 정리
                    
                    # 북마크 메타데이터 생성
                    bookmark_meta = data_helper.get_html_metadata(html_file)
                    source_id = f"html_bookmark_{html_file.replace('.html', '')}"
                    
                    logger.info(f"   📝 제목: {bookmark_meta['title']}")
                    logger.info(f"   🏷️ 키워드: {bookmark_meta['keywords']}")
                    logger.info(f"   📊 텍스트 길이: {len(text_content)} 문자")
                    
                    # 벡터 서비스로 저장
                    saved_vectors = await vector_service.save_document(
                        session=session,
                        user_id=user_id,  # 정수형 user_id
                        source_id=source_id,
                        source_type="bookmark_chunk",
                        content=text_content,
                        title=bookmark_meta['title'],
                        url=bookmark_meta['url'],
                        keywords=bookmark_meta['keywords'],
                        summary=bookmark_meta['description'],
                        extra_metadata={
                            "original_file": html_file,
                            "test_type": "html_bookmark",
                            "category": bookmark_meta.get('category', 'general')
                        }
                    )
                    
                    if saved_vectors:
                        logger.info(f"   ✅ 저장 완료: {len(saved_vectors)}개 청크")
                        saved_bookmarks.append({
                            "source_id": source_id,
                            "title": bookmark_meta['title'],
                            "keywords": bookmark_meta['keywords'],
                            "chunks": len(saved_vectors)
                        })
                    else:
                        logger.error(f"   ❌ 저장 실패: {html_file}")
                
                # 저장 결과 요약
                logger.info(f"\n📊 저장 완료 요약:")
                logger.info(f"   👤 사용자: {user_id}")
                logger.info(f"   📚 총 북마크: {len(saved_bookmarks)}개")
                total_chunks = sum(bookmark['chunks'] for bookmark in saved_bookmarks)
                logger.info(f"   📄 총 청크: {total_chunks}개")
                
                # 다양한 검색 테스트
                await test_searches(session, vector_service, user_id)
                
            except Exception as e:
                logger.error(f"❌ HTML 북마크 테스트 실패: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()
                
    except Exception as e:
        logger.error(f"❌ HTML 북마크 테스트 실패: {e}")
        raise

async def test_searches(session, vector_service, user_id):
    """다양한 검색 테스트"""
    logger.info(f"\n🔍 검색 테스트 시작")
    
    search_queries = [
        ("AI와 딥러닝", "AI/ML 관련 검색"),
        ("웹 개발과 프론트엔드", "웹 개발 관련 검색"),
        ("데이터 사이언스", "데이터 분석 관련 검색"),
        ("블록체인 기술", "블록체인 관련 검색"),
        ("파이썬 프로그래밍", "프로그래밍 언어 검색"),
        ("투자와 암호화폐", "투자 관련 검색")
    ]
    
    for query, description in search_queries:
        logger.info(f"\n🔍 {description}: '{query}'")
        logger.info("-" * 40)
        
        # 해당 사용자의 북마크에서 검색
        results = await vector_service.similarity_search(
            session=session,
            query=query,
            user_id=user_id,  # 정수형 user_id
            source_types=["bookmark_chunk"],
            limit=3,
            similarity_threshold=0.3
        )
        
        if results:
            logger.info(f"✅ {len(results)}개 결과:")
            for i, (doc, score) in enumerate(results, 1):
                category = doc.extra_metadata.get('category', '일반') if doc.extra_metadata else '일반'
                logger.info(f"   {i}. {doc.title} (유사도: {score:.4f})")
                logger.info(f"      카테고리: {category}")
                logger.info(f"      키워드: {doc.keywords}")
        else:
            logger.info("   검색 결과 없음")

if __name__ == "__main__":
    asyncio.run(test_html_bookmarks()) 