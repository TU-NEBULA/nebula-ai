#!/usr/bin/env python3
"""
user_id 컬럼을 VARCHAR에서 INTEGER로 변경하는 마이그레이션 스크립트
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_async_session
from sqlalchemy import text
from loguru import logger

async def migrate_user_id_to_integer():
    """user_id 컬럼을 VARCHAR에서 INTEGER로 변경"""
    logger.info("🔄 user_id 컬럼 타입 변경 마이그레이션 시작")
    
    async for session in get_async_session():
        try:
            # 1. 기존 데이터 확인
            logger.info("📊 기존 데이터 확인...")
            result = await session.execute(text("""
                SELECT DISTINCT user_id FROM document_vectors ORDER BY user_id;
            """))
            existing_user_ids = result.fetchall()
            
            if existing_user_ids:
                logger.info(f"✅ 기존 user_id 값들: {[row.user_id for row in existing_user_ids]}")
                
                # 모든 값이 정수로 변환 가능한지 확인
                for row in existing_user_ids:
                    try:
                        int(row.user_id)
                        logger.info(f"   ✅ '{row.user_id}' → {int(row.user_id)} 변환 가능")
                    except ValueError:
                        logger.error(f"   ❌ '{row.user_id}'는 정수로 변환할 수 없습니다!")
                        raise ValueError(f"user_id '{row.user_id}'를 정수로 변환할 수 없습니다.")
            else:
                logger.info("📊 기존 데이터 없음")
            
            # 2. document_vectors 테이블의 user_id 컬럼 변경
            logger.info("🔄 document_vectors.user_id 컬럼 타입 변경...")
            await session.execute(text("""
                ALTER TABLE document_vectors 
                ALTER COLUMN user_id TYPE INTEGER USING user_id::INTEGER;
            """))
            logger.info("✅ document_vectors.user_id → INTEGER 변경 완료")
            
            # 3. 다른 테이블들도 확인 및 변경
            tables_to_check = ['chat_sessions', 'chat_messages', 'user_feedback', 'user_profiles']
            
            for table in tables_to_check:
                try:
                    # 테이블과 컬럼 존재 확인
                    result = await session.execute(text(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = '{table}' AND column_name = 'user_id';
                    """))
                    col_info = result.fetchone()
                    
                    if col_info:
                        if 'varchar' in col_info.data_type.lower() or 'character' in col_info.data_type.lower():
                            logger.info(f"🔄 {table}.user_id 컬럼 타입 변경...")
                            await session.execute(text(f"""
                                ALTER TABLE {table} 
                                ALTER COLUMN user_id TYPE INTEGER USING user_id::INTEGER;
                            """))
                            logger.info(f"✅ {table}.user_id → INTEGER 변경 완료")
                        else:
                            logger.info(f"📊 {table}.user_id는 이미 {col_info.data_type} 타입")
                    else:
                        logger.info(f"📊 {table}에 user_id 컬럼 없음")
                        
                except Exception as e:
                    logger.warning(f"⚠️ {table} 처리 중 오류: {e}")
            
            # 4. 변경 결과 확인
            logger.info("\n📋 변경 결과 확인:")
            all_tables = ['document_vectors'] + tables_to_check
            
            for table in all_tables:
                try:
                    result = await session.execute(text(f"""
                        SELECT column_name, data_type, udt_name
                        FROM information_schema.columns 
                        WHERE table_name = '{table}' AND column_name = 'user_id';
                    """))
                    col_info = result.fetchone()
                    
                    if col_info:
                        logger.info(f"   ✅ {table}.user_id: {col_info.data_type} ({col_info.udt_name})")
                    else:
                        logger.info(f"   📊 {table}: user_id 컬럼 없음")
                        
                except Exception as e:
                    logger.warning(f"   ⚠️ {table} 확인 실패: {e}")
            
            # 5. 실제 데이터 확인
            if existing_user_ids:
                logger.info("\n💾 변경된 데이터 확인:")
                result = await session.execute(text("""
                    SELECT DISTINCT 
                        user_id,
                        pg_typeof(user_id) as actual_type
                    FROM document_vectors 
                    ORDER BY user_id;
                """))
                
                new_user_ids = result.fetchall()
                for uid in new_user_ids:
                    logger.info(f"   👤 {uid.user_id} (타입: {uid.actual_type})")
            
            await session.commit()
            logger.info("🎉 마이그레이션 완료!")
            
        except Exception as e:
            logger.error(f"❌ 마이그레이션 실패: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

if __name__ == "__main__":
    asyncio.run(migrate_user_id_to_integer()) 