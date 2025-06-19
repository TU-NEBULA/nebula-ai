#!/usr/bin/env python3
"""
PostgreSQL에 pgvector 확장을 설치하는 스크립트
"""
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from app.core.config import settings
from loguru import logger

def install_pgvector():
    """PostgreSQL에 pgvector 확장을 설치합니다."""
    
    logger.info("🔍 PostgreSQL pgvector 확장 설치 시작")
    logger.info(f"🌍 DB 호스트: {settings.POSTGRES_HOST}")
    logger.info(f"🗃️ DB 이름: {settings.POSTGRES_DB}")
    
    try:
        # PostgreSQL에 연결
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            sslmode=settings.DB_SSL_MODE
        )
        
        cursor = conn.cursor()
        
        # 1. 현재 pgvector 확장 상태 확인
        logger.info("🔍 pgvector 확장 상태 확인...")
        cursor.execute("SELECT * FROM pg_extension WHERE extname = %s;", ('vector',))
        result = cursor.fetchone()
        
        if result:
            logger.info("✅ pgvector 확장이 이미 설치되어 있습니다!")
            logger.info(f"   확장 정보: {result}")
        else:
            logger.info("📦 pgvector 확장을 설치합니다...")
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
                logger.info("✅ pgvector 확장 설치 완료!")
            except Exception as e:
                logger.error(f"❌ pgvector 확장 설치 실패: {e}")
                if "could not open extension control file" in str(e):
                    logger.error("💡 RDS에서 pgvector가 지원되지 않거나 권한이 없습니다.")
                    logger.error("   - RDS 파라미터 그룹에서 shared_preload_libraries에 'vector' 추가 필요")
                    logger.error("   - 또는 Amazon RDS for PostgreSQL에서 pgvector 지원 버전 확인 필요")
                return False
        
        # 2. 설치 확인
        cursor.execute("SELECT * FROM pg_extension WHERE extname = %s;", ('vector',))
        result = cursor.fetchone()
        
        if result:
            logger.info("🎉 pgvector 확장이 성공적으로 설치되었습니다!")
            logger.info(f"   확장 정보: {result}")
            
            # 3. pgvector 기능 테스트
            logger.info("🧪 pgvector 기능 테스트...")
            cursor.execute("SELECT '[1,2,3]'::vector;")
            test_result = cursor.fetchone()
            logger.info(f"   벡터 생성 테스트: {test_result[0]}")
            
            cursor.close()
            conn.close()
            return True
        else:
            logger.error("❌ pgvector 확장 설치가 확인되지 않습니다.")
            cursor.close()
            conn.close()
            return False
            
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        return False

def check_rds_pgvector_support():
    """RDS에서 pgvector 지원 여부를 확인합니다."""
    
    logger.info("🔍 RDS pgvector 지원 여부 확인...")
    
    try:
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            sslmode=settings.DB_SSL_MODE
        )
        
        cursor = conn.cursor()
        
        # PostgreSQL 버전 확인
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        logger.info(f"📊 PostgreSQL 버전: {version}")
        
        # 사용 가능한 확장 목록 확인
        cursor.execute("SELECT name FROM pg_available_extensions WHERE name LIKE '%vector%';")
        available_extensions = cursor.fetchall()
        
        if available_extensions:
            logger.info("✅ 사용 가능한 벡터 관련 확장:")
            for ext in available_extensions:
                logger.info(f"   - {ext[0]}")
        else:
            logger.warning("⚠️ 벡터 관련 확장이 사용 가능하지 않습니다.")
            logger.info("💡 대안 방법:")
            logger.info("   1. PostgreSQL 버전을 업그레이드")
            logger.info("   2. 다른 RDS 인스턴스 타입 고려")
            logger.info("   3. 로컬 PostgreSQL 사용")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ RDS 확인 실패: {e}")

if __name__ == "__main__":
    logger.info("🚀 pgvector 설치 프로세스 시작")
    logger.info("=" * 60)
    
    # 1. RDS 지원 여부 확인
    check_rds_pgvector_support()
    
    logger.info("=" * 30)
    
    # 2. pgvector 설치 시도
    success = install_pgvector()
    
    logger.info("=" * 60)
    
    if success:
        logger.info("🎉 pgvector 설치 완료! 이제 document_vectors 테이블을 생성할 수 있습니다.")
        logger.info("📋 다음 단계: python scripts/init_database.py")
    else:
        logger.error("💥 pgvector 설치 실패!")
        logger.info("🔧 해결 방법:")
        logger.info("   1. RDS 파라미터 그룹 설정 확인")
        logger.info("   2. PostgreSQL 버전 확인 (13+ 권장)")
        logger.info("   3. 로컬 PostgreSQL 사용 고려") 