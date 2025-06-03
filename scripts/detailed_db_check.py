#!/usr/bin/env python3
"""
데이터베이스 상세 조회 스크립트
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_async_session
from sqlalchemy import text
from loguru import logger

async def detailed_check():
    """모든 테이블의 데이터를 상세히 확인합니다."""
    logger.info("🔍 데이터베이스 상세 조회 시작")
    
    async for session in get_async_session():
        try:
            # 1. document_vectors 테이블 상세 조회
            logger.info("📋 document_vectors 테이블 조회:")
            result = await session.execute(text("""
                SELECT 
                    user_id, 
                    source_id, 
                    source_type, 
                    chunk_index,
                    LEFT(content, 100) as content_preview,
                    title,
                    LEFT(url, 50) as url_preview,
                    keywords,
                    LEFT(summary, 50) as summary_preview,
                    created_at
                FROM document_vectors 
                ORDER BY created_at DESC 
                LIMIT 10;
            """))
            
            rows = result.fetchall()
            if rows:
                logger.info(f"✅ {len(rows)}개의 북마크 데이터 발견:")
                for i, row in enumerate(rows, 1):
                    logger.info(f"   📚 {i}. 사용자: {row.user_id}")
                    logger.info(f"       소스: {row.source_id} ({row.source_type})")
                    logger.info(f"       청크: {row.chunk_index}")
                    logger.info(f"       제목: {row.title}")
                    logger.info(f"       URL: {row.url_preview}")
                    logger.info(f"       키워드: {row.keywords}")
                    logger.info(f"       내용: {row.content_preview}...")
                    logger.info(f"       요약: {row.summary_preview}")
                    logger.info(f"       생성: {row.created_at}")
                    logger.info("       " + "-"*50)
            else:
                logger.warning("⚠️ document_vectors 테이블이 비어있습니다.")
            
            # 2. 전체 테이블별 행 개수 확인
            logger.info("\n📊 모든 테이블의 데이터 개수:")
            tables = ['document_vectors', 'chat_sessions', 'chat_messages', 'rag_references', 'user_feedback', 'user_profiles']
            
            for table in tables:
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table};"))
                    count = result.scalar()
                    logger.info(f"   📋 {table}: {count}개")
                except Exception as e:
                    logger.error(f"   ❌ {table}: 조회 실패 - {e}")
            
            # 3. 최근 활동 확인
            logger.info("\n🕐 최근 1시간 내 생성된 데이터:")
            try:
                result = await session.execute(text("""
                    SELECT 
                        'document_vectors' as table_name,
                        COUNT(*) as count,
                        MAX(created_at) as latest
                    FROM document_vectors 
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                    
                    UNION ALL
                    
                    SELECT 
                        'chat_sessions' as table_name,
                        COUNT(*) as count,
                        MAX(created_at) as latest
                    FROM chat_sessions 
                    WHERE created_at > NOW() - INTERVAL '1 hour'
                    
                    ORDER BY latest DESC NULLS LAST;
                """))
                
                recent_rows = result.fetchall()
                for row in recent_rows:
                    if row.count > 0:
                        logger.info(f"   🆕 {row.table_name}: {row.count}개 (최신: {row.latest})")
                    
            except Exception as e:
                logger.error(f"❌ 최근 활동 조회 실패: {e}")
                
        except Exception as e:
            logger.error(f"❌ 데이터베이스 조회 실패: {e}")
        finally:
            await session.close()

if __name__ == "__main__":
    asyncio.run(detailed_check()) 