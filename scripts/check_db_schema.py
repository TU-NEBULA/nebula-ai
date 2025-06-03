#!/usr/bin/env python3
"""
PostgreSQL 데이터베이스 스키마 확인 스크립트
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_async_session
from sqlalchemy import text
from loguru import logger

async def check_database_schema():
    """데이터베이스 스키마를 상세히 확인합니다."""
    logger.info("🔍 PostgreSQL 데이터베이스 스키마 확인 시작")
    
    async for session in get_async_session():
        try:
            # 1. document_vectors 테이블의 상세 스키마 확인
            logger.info("📋 document_vectors 테이블 상세 스키마:")
            result = await session.execute(text("""
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default,
                    udt_name
                FROM information_schema.columns 
                WHERE table_name = 'document_vectors'
                ORDER BY ordinal_position;
            """))
            
            columns = result.fetchall()
            logger.info(f"✅ {len(columns)}개 컬럼 발견:")
            
            for col in columns:
                max_length = f"({col.character_maximum_length})" if col.character_maximum_length else ""
                default = f" DEFAULT {col.column_default}" if col.column_default else ""
                nullable = "NULL" if col.is_nullable == "YES" else "NOT NULL"
                
                logger.info(f"   📝 {col.column_name}:")
                logger.info(f"      타입: {col.data_type}{max_length}")
                logger.info(f"      UDT: {col.udt_name}")
                logger.info(f"      NULL 허용: {nullable}")
                if default:
                    logger.info(f"      기본값: {default}")
                logger.info("")
            
            # 2. user_id 컬럼에 특별히 집중
            logger.info("👤 user_id 컬럼 상세 분석:")
            user_id_col = next((col for col in columns if col.column_name == 'user_id'), None)
            if user_id_col:
                logger.info(f"   📊 데이터 타입: {user_id_col.data_type}")
                logger.info(f"   📏 최대 길이: {user_id_col.character_maximum_length}")
                logger.info(f"   🔧 UDT 이름: {user_id_col.udt_name}")
                logger.info(f"   ❓ NULL 허용: {user_id_col.is_nullable}")
            else:
                logger.error("   ❌ user_id 컬럼을 찾을 수 없습니다!")
            
            # 3. 다른 테이블들의 user_id 타입도 확인
            logger.info("\n📊 다른 테이블들의 user_id 컬럼 타입:")
            other_tables = ['chat_sessions', 'chat_messages', 'user_feedback', 'user_profiles']
            
            for table in other_tables:
                try:
                    result = await session.execute(text(f"""
                        SELECT 
                            column_name,
                            data_type,
                            character_maximum_length,
                            udt_name
                        FROM information_schema.columns 
                        WHERE table_name = '{table}' AND column_name = 'user_id';
                    """))
                    
                    col = result.fetchone()
                    if col:
                        max_length = f"({col.character_maximum_length})" if col.character_maximum_length else ""
                        logger.info(f"   📋 {table}.user_id: {col.data_type}{max_length} ({col.udt_name})")
                    else:
                        logger.info(f"   📋 {table}: user_id 컬럼 없음")
                        
                except Exception as e:
                    logger.warning(f"   ⚠️ {table} 확인 실패: {e}")
            
            # 4. 실제 저장된 user_id 값들의 타입 확인
            logger.info("\n💾 실제 저장된 user_id 값들:")
            result = await session.execute(text("""
                SELECT DISTINCT 
                    user_id,
                    pg_typeof(user_id) as actual_type,
                    source_type
                FROM document_vectors 
                ORDER BY user_id;
            """))
            
            user_ids = result.fetchall()
            if user_ids:
                logger.info(f"✅ {len(user_ids)}개의 서로 다른 user_id 발견:")
                for uid in user_ids:
                    logger.info(f"   👤 {uid.user_id} (타입: {uid.actual_type}, 소스: {uid.source_type})")
            else:
                logger.info("   📊 저장된 데이터 없음")
            
            # 5. 인덱스 정보 확인
            logger.info("\n🔗 user_id 관련 인덱스:")
            result = await session.execute(text("""
                SELECT 
                    indexname,
                    indexdef
                FROM pg_indexes 
                WHERE tablename = 'document_vectors' 
                  AND indexdef LIKE '%user_id%'
                ORDER BY indexname;
            """))
            
            indexes = result.fetchall()
            if indexes:
                for idx in indexes:
                    logger.info(f"   🔍 {idx.indexname}:")
                    logger.info(f"      {idx.indexdef}")
            else:
                logger.info("   📊 user_id 관련 인덱스 없음")
                
        except Exception as e:
            logger.error(f"❌ 스키마 확인 실패: {e}")
            raise
        finally:
            await session.close()

if __name__ == "__main__":
    asyncio.run(check_database_schema()) 