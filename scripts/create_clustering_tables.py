#!/usr/bin/env python3
"""
클러스터링 시스템 데이터베이스 테이블 생성 스크립트

이 스크립트는 사용자 프로파일 기반 클러스터링 시스템에 필요한
새로운 데이터베이스 테이블들을 생성합니다.

사용법:
    python scripts/create_clustering_tables.py

생성되는 테이블:
    - user_clusters: 클러스터 메타데이터
    - user_cluster_memberships: 사용자-클러스터 매핑
    - cluster_keywords: 클러스터별 특징 키워드
    - cluster_quality_metrics: 클러스터 품질 지표
    - clustering_job_history: 클러스터링 작업 이력
"""

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from loguru import logger
from app.core.config import settings
from app.models import *  # 모든 모델 임포트 (클러스터링 모델 포함)


async def create_clustering_tables():
    """클러스터링 테이블 생성"""
    
    # 데이터베이스 연결
    engine = create_async_engine(
        str(settings.ASYNC_DATABASE_URL),
        echo=True,
        future=True
    )
    
    try:
        logger.info("🚀 클러스터링 테이블 생성 시작...")
        
        # 테이블 생성 전 확인
        async with engine.begin() as conn:
            # pgvector 확장 확인
            result = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            if not result.fetchone():
                logger.warning("⚠️ pgvector 확장이 설치되지 않았습니다. 벡터 관련 기능이 제한될 수 있습니다.")
            
            # 기존 테이블 확인
            existing_tables = await conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN (
                        'user_clusters', 
                        'user_cluster_memberships', 
                        'cluster_keywords', 
                        'cluster_quality_metrics', 
                        'clustering_job_history'
                    )
                """)
            )
            
            existing_table_names = [row[0] for row in existing_tables.fetchall()]
            
            if existing_table_names:
                logger.warning(f"⚠️ 다음 테이블들이 이미 존재합니다: {existing_table_names}")
                response = input("계속 진행하시겠습니까? (기존 테이블은 삭제되지 않습니다) [y/N]: ")
                if response.lower() != 'y':
                    logger.info("작업이 취소되었습니다.")
                    return
        
        # 모든 모델의 메타데이터를 기반으로 테이블 생성
        from app.models.base import BaseModel
        async with engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.create_all)
        
        logger.info("✅ 클러스터링 테이블 생성 완료!")
        
        # 생성된 테이블 확인
        async with engine.begin() as conn:
            tables_result = await conn.execute(
                text("""
                    SELECT table_name, 
                           (SELECT COUNT(*) FROM information_schema.columns 
                            WHERE table_name = t.table_name AND table_schema = 'public') as column_count
                    FROM information_schema.tables t
                    WHERE table_schema = 'public' 
                    AND table_name LIKE '%cluster%'
                    ORDER BY table_name
                """)
            )
            
            tables = tables_result.fetchall()
            
            logger.info("📋 생성된 클러스터링 관련 테이블:")
            for table_name, column_count in tables:
                logger.info(f"  - {table_name} ({column_count}개 컬럼)")
        
        # 인덱스 추가 (성능 최적화)
        await create_indexes(engine)
        
        logger.info("🎯 클러스터링 시스템 데이터베이스 준비 완료!")
        
    except Exception as e:
        logger.error(f"❌ 테이블 생성 실패: {str(e)}")
        raise
    finally:
        await engine.dispose()


async def create_indexes(engine):
    """성능 최적화를 위한 인덱스 생성"""
    
    indexes = [
        # 사용자 클러스터 멤버십 인덱스
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_cluster_memberships_user_id ON user_cluster_memberships(user_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_cluster_memberships_cluster_id ON user_cluster_memberships(cluster_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_cluster_memberships_confidence ON user_cluster_memberships(confidence_score DESC)",
        
        # 클러스터 인덱스
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_clusters_active ON user_clusters(is_active) WHERE is_active = true",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_clusters_size ON user_clusters(size DESC)",
        
        # 클러스터 키워드 인덱스
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cluster_keywords_cluster_id ON cluster_keywords(cluster_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cluster_keywords_weight ON cluster_keywords(weight DESC)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cluster_keywords_keyword ON cluster_keywords(keyword)",
        
        # 품질 지표 인덱스
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cluster_quality_metrics_cluster_id ON cluster_quality_metrics(cluster_id)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cluster_quality_metrics_measured_at ON cluster_quality_metrics(measured_at DESC)",
        
        # 작업 이력 인덱스
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clustering_job_history_status ON clustering_job_history(status)",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_clustering_job_history_started_at ON clustering_job_history(started_at DESC)",
    ]
    
    logger.info("🔧 성능 최적화 인덱스 생성 중...")
    
    async with engine.begin() as conn:
        for index_sql in indexes:
            try:
                await conn.execute(text(index_sql))
                index_name = index_sql.split("idx_")[1].split(" ")[0] if "idx_" in index_sql else "unknown"
                logger.info(f"  ✅ 인덱스 생성됨: idx_{index_name}")
            except Exception as e:
                logger.warning(f"  ⚠️ 인덱스 생성 실패: {str(e)}")
    
    logger.info("✅ 인덱스 생성 완료!")


async def check_prerequisites():
    """전제 조건 확인"""
    
    logger.info("🔍 전제 조건 확인 중...")
    
    # 데이터베이스 연결 테스트
    engine = create_async_engine(str(settings.ASYNC_DATABASE_URL), echo=False)
    
    try:
        async with engine.begin() as conn:
            # 연결 테스트
            await conn.execute(text("SELECT 1"))
            logger.info("  ✅ 데이터베이스 연결 성공")
            
            # PostgreSQL 버전 확인
            version_result = await conn.execute(text("SELECT version()"))
            version = version_result.fetchone()[0]
            logger.info(f"  📊 PostgreSQL 버전: {version}")
            
            # pgvector 확장 확인
            pgvector_result = await conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            if pgvector_result.fetchone():
                logger.info("  ✅ pgvector 확장 설치됨")
            else:
                logger.warning("  ⚠️ pgvector 확장이 설치되지 않음 (선택사항)")
            
            # 기존 사용자 프로파일 테이블 확인
            user_profile_result = await conn.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'user_profiles'")
            )
            if user_profile_result.fetchone()[0] > 0:
                logger.info("  ✅ 기존 user_profiles 테이블 존재")
                
                # 사용자 데이터 확인
                user_count_result = await conn.execute(text("SELECT COUNT(*) FROM user_profiles"))
                user_count = user_count_result.fetchone()[0]
                logger.info(f"  📈 등록된 사용자 프로파일: {user_count}개")
                
                if user_count < 10:
                    logger.warning("  ⚠️ 클러스터링을 위한 최소 사용자 수가 부족할 수 있습니다 (권장: 50명 이상)")
            else:
                logger.warning("  ⚠️ user_profiles 테이블이 존재하지 않습니다")
    
    except Exception as e:
        logger.error(f"  ❌ 전제 조건 확인 실패: {str(e)}")
        raise
    finally:
        await engine.dispose()
    
    logger.info("✅ 전제 조건 확인 완료!")


async def main():
    """메인 실행 함수"""
    
    logger.info("=" * 60)
    logger.info("🎯 클러스터링 시스템 데이터베이스 설정")
    logger.info("=" * 60)
    
    try:
        # 1. 전제 조건 확인
        await check_prerequisites()
        print()
        
        # 2. 테이블 생성
        await create_clustering_tables()
        print()
        
        logger.info("🎉 클러스터링 시스템 데이터베이스 설정이 완료되었습니다!")
        logger.info("")
        logger.info("다음 단계:")
        logger.info("1. 클러스터링 서비스를 사용하여 초기 클러스터링 수행")
        logger.info("2. 주기적 클러스터링 작업 스케줄 설정")
        logger.info("3. 추천 시스템과 연동")
        
    except Exception as e:
        logger.error(f"💥 설정 실패: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 