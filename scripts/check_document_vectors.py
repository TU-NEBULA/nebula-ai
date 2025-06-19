#!/usr/bin/env python3
"""
document_vectors 테이블 생성 확인 스크립트
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_async_session
from sqlalchemy import text
from loguru import logger

async def check_tables():
    """생성된 테이블들을 확인합니다."""
    logger.info("🔍 PostgreSQL 테이블 생성 확인")
    
    async for session in get_async_session():
        try:
            # 1. 전체 테이블 목록 확인
            result = await session.execute(text("""
                SELECT table_name, table_type 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """))
            
            tables = result.fetchall()
            logger.info(f"📋 생성된 테이블 목록 ({len(tables)}개):")
            for table in tables:
                logger.info(f"  ✅ {table[0]} ({table[1]})")
            
            # 2. document_vectors 테이블 확인
            document_vectors_exists = any(table[0] == 'document_vectors' for table in tables)
            
            if document_vectors_exists:
                logger.info("\n🎉 document_vectors 테이블이 성공적으로 생성되었습니다!")
                
                # 3. document_vectors 테이블 구조 확인
                result = await session.execute(text("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = 'document_vectors'
                    ORDER BY ordinal_position;
                """))
                
                columns = result.fetchall()
                logger.info(f"\n📊 document_vectors 테이블 구조 ({len(columns)}개 컬럼):")
                for col in columns:
                    default = f" (default: {col[3]})" if col[3] else ""
                    logger.info(f"  📝 {col[0]}: {col[1]} (nullable: {col[2]}){default}")
                
                # 4. 인덱스 확인
                result = await session.execute(text("""
                    SELECT indexname, indexdef 
                    FROM pg_indexes 
                    WHERE tablename = 'document_vectors'
                    ORDER BY indexname;
                """))
                
                indexes = result.fetchall()
                logger.info(f"\n🔗 document_vectors 인덱스 ({len(indexes)}개):")
                for idx in indexes:
                    logger.info(f"  🔍 {idx[0]}")
                    logger.info(f"      {idx[1]}")
                
                # 5. pgvector 확장 확인
                result = await session.execute(text("""
                    SELECT extname, extversion 
                    FROM pg_extension 
                    WHERE extname = 'vector';
                """))
                
                vector_ext = result.fetchone()
                if vector_ext:
                    logger.info(f"\n🚀 pgvector 확장: {vector_ext[0]} v{vector_ext[1]}")
                
                # 6. 데이터 개수 확인
                result = await session.execute(text("SELECT COUNT(*) FROM document_vectors;"))
                count = result.fetchone()[0]
                logger.info(f"\n📈 현재 저장된 벡터 데이터: {count}개")
                
            else:
                logger.error("❌ document_vectors 테이블이 생성되지 않았습니다!")
                logger.info("💡 해결 방법:")
                logger.info("   1. python scripts/install_pgvector.py")
                logger.info("   2. python scripts/init_database.py")
            
        except Exception as e:
            logger.error(f"❌ 테이블 확인 중 오류: {e}")
        
        break

async def test_vector_operations():
    """간단한 벡터 연산 테스트"""
    logger.info("\n🧪 벡터 연산 테스트")
    
    async for session in get_async_session():
        try:
            # 벡터 생성 테스트
            result = await session.execute(text("SELECT '[1,2,3]'::vector;"))
            vector = result.fetchone()[0]
            logger.info(f"  ✅ 벡터 생성: {vector}")
            
            # 벡터 유사도 테스트
            result = await session.execute(text("""
                SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector as distance;
            """))
            distance = result.fetchone()[0]
            logger.info(f"  ✅ 코사인 거리: {distance}")
            
        except Exception as e:
            logger.error(f"❌ 벡터 연산 테스트 실패: {e}")
        
        break

if __name__ == "__main__":
    logger.info("🚀 document_vectors 테이블 확인 시작")
    logger.info("=" * 60)
    
    asyncio.run(check_tables())
    asyncio.run(test_vector_operations())
    
    logger.info("=" * 60)
    logger.info("🎉 확인 완료!")
    logger.info("\n📋 DBeaver 확인 방법:")
    logger.info("   1. DBeaver에서 F5 (새로고침) 누르기")
    logger.info("   2. Tables > document_vectors 확인")
    logger.info("   3. 테이블 우클릭 > 'View DDL' 로 구조 확인") 