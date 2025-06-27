"""
추천 피드백 수집 및 학습 서비스

사용자의 추천 상호작용을 수집하고 분석하여
추천 시스템의 성능을 지속적으로 개선합니다.
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json
import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlmodel import SQLModel, Field

from app.core.database import get_async_session
from app.models.user_profile import UserProfile
from app.models.bookmark import Bookmark
from app.services.vector_service import VectorService
from app.repositories.user_profile_repository import UserProfileRepository


class FeedbackAction(str, Enum):
    """피드백 액션 타입"""
    CLICKED = "clicked"
    SAVED = "saved"
    DISMISSED = "dismissed"
    IGNORED = "ignored"
    SHARED = "shared"
    BOOKMARKED = "bookmarked"


class RecommendationSource(str, Enum):
    """추천 소스 타입"""
    CONTENT_BASED = "content_based"
    COLLABORATIVE = "collaborative"
    HYBRID = "hybrid"
    SEARCH_BASED = "search_based"
    TRENDING = "trending"


@dataclass
class FeedbackEvent:
    """피드백 이벤트 데이터"""
    user_id: int
    recommendation_id: str
    action: FeedbackAction
    timestamp: datetime
    session_id: Optional[str] = None
    source: Optional[RecommendationSource] = None
    metadata: Dict[str, Any] = None


class RecommendationFeedback(SQLModel, table=True):
    """추천 피드백 모델"""
    __tablename__ = "recommendation_feedback"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    recommendation_id: str = Field(index=True)
    action: str  # FeedbackAction
    source: Optional[str] = None  # RecommendationSource
    session_id: Optional[str] = Field(index=True)
    
    # 추천 메타데이터
    document_id: Optional[int] = None
    recommendation_score: Optional[float] = None
    recommendation_type: Optional[str] = None
    
    # 피드백 메타데이터
    time_to_action: Optional[float] = None  # 추천 제시부터 액션까지 시간(초)
    scroll_depth: Optional[float] = None
    session_duration: Optional[int] = None
    device_type: Optional[str] = None
    
    # 시간 정보
    created_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    
    # 학습에 사용된 여부
    used_for_training: bool = Field(default=False)


class RecommendationPerformanceMetrics(SQLModel, table=True):
    """추천 성과 지표 모델"""
    __tablename__ = "recommendation_performance_metrics"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime = Field(index=True)
    user_id: Optional[int] = Field(index=True)  # null이면 전체 평균
    
    # 성과 지표
    total_recommendations: int = 0
    click_through_rate: float = 0.0
    save_rate: float = 0.0
    dismiss_rate: float = 0.0
    
    # 품질 지표
    avg_time_to_action: float = 0.0
    avg_recommendation_score: float = 0.0
    diversity_score: float = 0.0
    
    # 소스별 성과
    content_based_ctr: float = 0.0
    collaborative_ctr: float = 0.0
    hybrid_ctr: float = 0.0
    search_based_ctr: float = 0.0
    
    created_at: datetime = Field(default_factory=datetime.now)


class RecommendationFeedbackService:
    """추천 피드백 수집 및 분석 서비스"""

    def __init__(self):
        self.vector_service = VectorService()
        self.profile_repository = UserProfileRepository()
        
        # 피드백 처리 설정
        self.feedback_batch_size = 50
        self.processing_interval = 60  # 초
        
        # 성과 분석 설정
        self.min_feedback_count = 10  # 분석을 위한 최소 피드백 수
        self.learning_rate = 0.1  # 학습률
        
        # 백그라운드 처리 상태
        self.is_processing = False
        self.feedback_queue = asyncio.Queue()

    async def record_feedback(
        self,
        user_id: int,
        recommendation_id: str,
        action: FeedbackAction,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        추천 피드백 기록
        
        Args:
            user_id: 사용자 ID
            recommendation_id: 추천 ID (UUID)
            action: 사용자 액션
            session_id: 세션 ID
            metadata: 추가 메타데이터
            
        Returns:
            기록 결과
        """
        try:
            async for session in get_async_session():
                # 피드백 레코드 생성
                feedback_record = RecommendationFeedback(
                    user_id=user_id,
                    recommendation_id=recommendation_id,
                    action=action.value,
                    session_id=session_id,
                    **self._extract_metadata(metadata or {})
                )
                
                session.add(feedback_record)
                await session.commit()
                await session.refresh(feedback_record)
                
                # 피드백 이벤트를 큐에 추가 (비동기 처리용)
                feedback_event = FeedbackEvent(
                    user_id=user_id,
                    recommendation_id=recommendation_id,
                    action=action,
                    timestamp=datetime.now(),
                    session_id=session_id,
                    metadata=metadata
                )
                
                await self.feedback_queue.put(feedback_event)
                
                logger.info(f"피드백 기록 완료: User {user_id}, Action {action.value}")
                
                return {
                    "feedback_id": feedback_record.id,
                    "user_id": user_id,
                    "recommendation_id": recommendation_id,
                    "action": action.value,
                    "recorded_at": feedback_record.created_at,
                    "status": "recorded"
                }
                
        except Exception as e:
            logger.error(f"❌ 피드백 기록 실패: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }

    async def get_user_feedback_history(
        self,
        user_id: int,
        limit: int = 100,
        action_filter: Optional[FeedbackAction] = None
    ) -> List[Dict[str, Any]]:
        """
        사용자 피드백 히스토리 조회
        
        Args:
            user_id: 사용자 ID
            limit: 반환할 레코드 수
            action_filter: 액션 필터
            
        Returns:
            피드백 히스토리 리스트
        """
        try:
            async for session in get_async_session():
                query = select(RecommendationFeedback).where(
                    RecommendationFeedback.user_id == user_id
                )
                
                if action_filter:
                    query = query.where(RecommendationFeedback.action == action_filter.value)
                
                query = query.order_by(desc(RecommendationFeedback.created_at)).limit(limit)
                
                result = await session.execute(query)
                feedback_records = result.scalars().all()
                
                return [
                    {
                        "id": record.id,
                        "recommendation_id": record.recommendation_id,
                        "action": record.action,
                        "source": record.source,
                        "session_id": record.session_id,
                        "time_to_action": record.time_to_action,
                        "created_at": record.created_at
                    }
                    for record in feedback_records
                ]
                
        except Exception as e:
            logger.error(f"❌ 피드백 히스토리 조회 실패: {e}")
            return []

    async def analyze_recommendation_performance(
        self,
        user_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        추천 성과 분석
        
        Args:
            user_id: 특정 사용자 분석 (None이면 전체)
            date_from: 분석 시작 날짜
            date_to: 분석 종료 날짜
            
        Returns:
            성과 분석 결과
        """
        try:
            if not date_from:
                date_from = datetime.now() - timedelta(days=30)
            if not date_to:
                date_to = datetime.now()
                
            async for session in get_async_session():
                # 기본 쿼리 조건
                base_conditions = [
                    RecommendationFeedback.created_at >= date_from,
                    RecommendationFeedback.created_at <= date_to
                ]
                
                if user_id:
                    base_conditions.append(RecommendationFeedback.user_id == user_id)
                
                # 총 추천 수와 액션별 통계
                stats_query = select(
                    func.count(RecommendationFeedback.id).label('total_recommendations'),
                    func.sum(
                        func.case((RecommendationFeedback.action == 'clicked', 1), else_=0)
                    ).label('clicks'),
                    func.sum(
                        func.case((RecommendationFeedback.action == 'saved', 1), else_=0)
                    ).label('saves'),
                    func.sum(
                        func.case((RecommendationFeedback.action == 'dismissed', 1), else_=0)
                    ).label('dismissals'),
                    func.avg(RecommendationFeedback.time_to_action).label('avg_time_to_action'),
                    func.avg(RecommendationFeedback.recommendation_score).label('avg_rec_score')
                ).where(and_(*base_conditions))
                
                stats_result = await session.execute(stats_query)
                stats = stats_result.first()
                
                total_recs = stats.total_recommendations or 0
                
                if total_recs == 0:
                    return {
                        "period": {"from": date_from, "to": date_to},
                        "user_id": user_id,
                        "total_recommendations": 0,
                        "message": "분석할 데이터가 없습니다."
                    }
                
                # 성과 지표 계산
                click_rate = (stats.clicks or 0) / total_recs
                save_rate = (stats.saves or 0) / total_recs
                dismiss_rate = (stats.dismissals or 0) / total_recs
                
                # 소스별 성과 분석
                source_performance = await self._analyze_source_performance(
                    session, base_conditions
                )
                
                # 시간대별 성과 분석
                temporal_analysis = await self._analyze_temporal_performance(
                    session, base_conditions
                )
                
                # 다양성 점수 계산
                diversity_score = await self._calculate_diversity_score(
                    session, base_conditions
                )
                
                return {
                    "period": {"from": date_from, "to": date_to},
                    "user_id": user_id,
                    "overview": {
                        "total_recommendations": total_recs,
                        "click_through_rate": round(click_rate, 4),
                        "save_rate": round(save_rate, 4),
                        "dismiss_rate": round(dismiss_rate, 4),
                        "avg_time_to_action": round(stats.avg_time_to_action or 0, 2),
                        "avg_recommendation_score": round(stats.avg_rec_score or 0, 4)
                    },
                    "source_performance": source_performance,
                    "temporal_analysis": temporal_analysis,
                    "quality_metrics": {
                        "diversity_score": diversity_score,
                        "engagement_rate": round(click_rate + save_rate, 4),
                        "satisfaction_rate": round(1 - dismiss_rate, 4)
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ 추천 성과 분석 실패: {e}")
            return {"error": str(e)}

    async def start_background_processing(self):
        """백그라운드 피드백 처리 시작"""
        if self.is_processing:
            logger.warning("피드백 처리가 이미 실행 중입니다.")
            return
            
        self.is_processing = True
        logger.info("🚀 추천 피드백 백그라운드 처리 시작")
        
        # 백그라운드 태스크들 시작
        asyncio.create_task(self._process_feedback_queue())
        asyncio.create_task(self._periodic_performance_calculation())

    async def stop_background_processing(self):
        """백그라운드 피드백 처리 중지"""
        self.is_processing = False
        logger.info("🛑 추천 피드백 백그라운드 처리 중지")

    async def _process_feedback_queue(self):
        """피드백 큐 처리"""
        while self.is_processing:
            try:
                feedback_batch = []
                
                # 배치 수집
                try:
                    first_feedback = await asyncio.wait_for(
                        self.feedback_queue.get(), 
                        timeout=self.processing_interval
                    )
                    feedback_batch.append(first_feedback)
                    
                    # 추가 피드백 수집
                    for _ in range(self.feedback_batch_size - 1):
                        try:
                            feedback = await asyncio.wait_for(
                                self.feedback_queue.get(), 
                                timeout=1.0
                            )
                            feedback_batch.append(feedback)
                        except asyncio.TimeoutError:
                            break
                            
                except asyncio.TimeoutError:
                    continue
                
                if feedback_batch:
                    await self._process_feedback_batch(feedback_batch)
                    
            except Exception as e:
                logger.error(f"❌ 피드백 큐 처리 중 오류: {e}")
                await asyncio.sleep(10)

    async def _process_feedback_batch(self, feedback_batch: List[FeedbackEvent]):
        """피드백 배치 처리"""
        try:
            logger.info(f"📦 피드백 배치 처리: {len(feedback_batch)}개")
            
            # 사용자별 피드백 패턴 분석
            user_patterns = {}
            for feedback in feedback_batch:
                user_id = feedback.user_id
                if user_id not in user_patterns:
                    user_patterns[user_id] = {
                        "positive_actions": 0,
                        "negative_actions": 0,
                        "total_actions": 0
                    }
                
                user_patterns[user_id]["total_actions"] += 1
                
                if feedback.action in [FeedbackAction.CLICKED, FeedbackAction.SAVED]:
                    user_patterns[user_id]["positive_actions"] += 1
                elif feedback.action == FeedbackAction.DISMISSED:
                    user_patterns[user_id]["negative_actions"] += 1
            
            # 패턴 기반 프로파일 조정 (향후 ML 모델 통합 지점)
            await self._adjust_user_preferences(user_patterns)
            
            logger.info(f"✅ 피드백 배치 처리 완료: {len(feedback_batch)}개")
            
        except Exception as e:
            logger.error(f"❌ 피드백 배치 처리 실패: {e}")

    async def _periodic_performance_calculation(self):
        """주기적 성과 계산"""
        while self.is_processing:
            try:
                await asyncio.sleep(3600)  # 1시간마다
                
                # 일일 성과 메트릭 계산 및 저장
                await self._calculate_and_store_daily_metrics()
                
                logger.info("📊 일일 성과 메트릭 계산 완료")
                
            except Exception as e:
                logger.error(f"❌ 주기적 성과 계산 실패: {e}")

    # === Helper Methods ===
    
    def _extract_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """메타데이터에서 필요한 필드 추출"""
        return {
            "time_to_action": metadata.get("time_to_action"),
            "scroll_depth": metadata.get("scroll_depth"),
            "session_duration": metadata.get("session_duration"),
            "device_type": metadata.get("device_type"),
            "document_id": metadata.get("document_id"),
            "recommendation_score": metadata.get("recommendation_score"),
            "recommendation_type": metadata.get("recommendation_type"),
            "source": metadata.get("source")
        }

    async def _analyze_source_performance(
        self, session: AsyncSession, base_conditions: List
    ) -> Dict[str, Dict[str, float]]:
        """소스별 성과 분석"""
        try:
            source_query = select(
                RecommendationFeedback.source,
                func.count(RecommendationFeedback.id).label('total'),
                func.sum(
                    func.case((RecommendationFeedback.action == 'clicked', 1), else_=0)
                ).label('clicks'),
                func.sum(
                    func.case((RecommendationFeedback.action == 'saved', 1), else_=0)
                ).label('saves')
            ).where(and_(*base_conditions)).group_by(RecommendationFeedback.source)
            
            source_result = await session.execute(source_query)
            source_stats = source_result.all()
            
            performance = {}
            for stat in source_stats:
                if stat.source and stat.total > 0:
                    performance[stat.source] = {
                        "total_recommendations": stat.total,
                        "click_rate": (stat.clicks or 0) / stat.total,
                        "save_rate": (stat.saves or 0) / stat.total,
                        "engagement_rate": ((stat.clicks or 0) + (stat.saves or 0)) / stat.total
                    }
            
            return performance
            
        except Exception as e:
            logger.error(f"❌ 소스별 성과 분석 실패: {e}")
            return {}

    async def _analyze_temporal_performance(
        self, session: AsyncSession, base_conditions: List
    ) -> Dict[str, Any]:
        """시간대별 성과 분석"""
        try:
            # 시간대별 클릭률 분석
            hourly_query = select(
                func.extract('hour', RecommendationFeedback.created_at).label('hour'),
                func.count(RecommendationFeedback.id).label('total'),
                func.sum(
                    func.case((RecommendationFeedback.action == 'clicked', 1), else_=0)
                ).label('clicks')
            ).where(and_(*base_conditions)).group_by('hour')
            
            hourly_result = await session.execute(hourly_query)
            hourly_stats = hourly_result.all()
            
            hourly_performance = {}
            for stat in hourly_stats:
                if stat.total > 0:
                    hourly_performance[int(stat.hour)] = {
                        "total": stat.total,
                        "click_rate": (stat.clicks or 0) / stat.total
                    }
            
            return {"hourly_performance": hourly_performance}
            
        except Exception as e:
            logger.error(f"❌ 시간대별 성과 분석 실패: {e}")
            return {}

    async def _calculate_diversity_score(
        self, session: AsyncSession, base_conditions: List
    ) -> float:
        """추천 다양성 점수 계산"""
        try:
            # 문서 ID 기반 다양성 계산 (단순화된 버전)
            diversity_query = select(
                func.count(func.distinct(RecommendationFeedback.document_id)).label('unique_docs'),
                func.count(RecommendationFeedback.id).label('total_recs')
            ).where(and_(*base_conditions))
            
            diversity_result = await session.execute(diversity_query)
            diversity_stat = diversity_result.first()
            
            if diversity_stat.total_recs > 0:
                return diversity_stat.unique_docs / diversity_stat.total_recs
            
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ 다양성 점수 계산 실패: {e}")
            return 0.0

    async def _adjust_user_preferences(self, user_patterns: Dict[int, Dict[str, int]]):
        """사용자 선호도 조정"""
        try:
            async for session in get_async_session():
                for user_id, pattern in user_patterns.items():
                    total_actions = pattern["total_actions"]
                    if total_actions < self.min_feedback_count:
                        continue
                    
                    # 긍정적 피드백 비율 계산
                    positive_ratio = pattern["positive_actions"] / total_actions
                    
                    # 사용자 프로파일 조정 (향후 구현)
                    # 현재는 로그만 기록
                    logger.debug(
                        f"사용자 {user_id} 선호도 패턴: "
                        f"긍정 {positive_ratio:.2f}, 총 액션 {total_actions}"
                    )
                    
        except Exception as e:
            logger.error(f"❌ 사용자 선호도 조정 실패: {e}")

    async def _calculate_and_store_daily_metrics(self):
        """일일 메트릭 계산 및 저장"""
        try:
            today = datetime.now().date()
            date_from = datetime.combine(today, datetime.min.time())
            date_to = datetime.combine(today, datetime.max.time())
            
            # 전체 성과 계산
            overall_performance = await self.analyze_recommendation_performance(
                date_from=date_from, date_to=date_to
            )
            
            # 메트릭 저장 (구현 필요시)
            logger.info(f"일일 메트릭 계산 완료: {today}")
            
        except Exception as e:
            logger.error(f"❌ 일일 메트릭 계산 실패: {e}")

    async def get_feedback_summary(self, user_id: int) -> Dict[str, Any]:
        """사용자 피드백 요약 조회"""
        try:
            async for session in get_async_session():
                # 최근 30일 피드백 요약
                date_from = datetime.now() - timedelta(days=30)
                
                summary_query = select(
                    func.count(RecommendationFeedback.id).label('total_feedback'),
                    func.sum(
                        func.case((RecommendationFeedback.action == 'clicked', 1), else_=0)
                    ).label('clicks'),
                    func.sum(
                        func.case((RecommendationFeedback.action == 'saved', 1), else_=0)
                    ).label('saves'),
                    func.sum(
                        func.case((RecommendationFeedback.action == 'dismissed', 1), else_=0)
                    ).label('dismissals')
                ).where(
                    and_(
                        RecommendationFeedback.user_id == user_id,
                        RecommendationFeedback.created_at >= date_from
                    )
                )
                
                result = await session.execute(summary_query)
                stats = result.first()
                
                total = stats.total_feedback or 0
                if total == 0:
                    return {
                        "user_id": user_id,
                        "period_days": 30,
                        "total_feedback": 0,
                        "engagement_level": "none"
                    }
                
                clicks = stats.clicks or 0
                saves = stats.saves or 0
                dismissals = stats.dismissals or 0
                
                engagement_rate = (clicks + saves) / total
                
                # 참여도 레벨 결정
                if engagement_rate >= 0.7:
                    engagement_level = "high"
                elif engagement_rate >= 0.3:
                    engagement_level = "medium"
                else:
                    engagement_level = "low"
                
                return {
                    "user_id": user_id,
                    "period_days": 30,
                    "total_feedback": total,
                    "clicks": clicks,
                    "saves": saves,
                    "dismissals": dismissals,
                    "engagement_rate": round(engagement_rate, 4),
                    "engagement_level": engagement_level
                }
                
        except Exception as e:
            logger.error(f"❌ 피드백 요약 조회 실패: {e}")
            return {"error": str(e)} 