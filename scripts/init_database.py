#!/usr/bin/env python3
"""
데이터베이스 초기화 스크립트

이 스크립트는 프로젝트에 필요한 모든 데이터베이스 테이블을 생성합니다.
"""

import asyncio
import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import SQLModel
from app.core.database import engine
from app.models.user_profile import UserProfile
from app.models.bookmark import Bookmark
from app.models.chat import Chat
from app.models.clustering import UserCluster, ClusteringMetadata
from app.models.extract_data import DocumentVector
from app.services.recommendation_feedback import RecommendationFeedback, RecommendationPerformanceMetrics

async def init_database():
    """데이터베이스 초기화"""
    async with engine.begin() as conn:
        # 모든 테이블 생성
        await conn.run_sync(SQLModel.metadata.create_all)
        print("✅ 모든 테이블이 성공적으로 생성되었습니다.")
        
        # 생성된 테이블 목록 출력
        tables = [
            "user_profiles",
            "bookmarks", 
            "chats",
            "user_clusters",
            "clustering_metadata",
            "document_vectors",
            "recommendation_feedback",
            "recommendation_performance_metrics"
        ]
        
        print("\n📋 생성된 테이블 목록:")
        for table in tables:
            print(f"  - {table}")
        
        print("\n🎯 추천 시스템 데이터 파이프라인 구축 완료!")

if __name__ == "__main__":
    asyncio.run(init_database())
