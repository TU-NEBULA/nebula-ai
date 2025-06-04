"""
일일 프로필 품질 모니터링 및 자동 업데이트 시스템

이 모듈은 매일 모든 사용자 프로필의 품질을 체크하고,
품질이 낮은 프로필들에 대해 자동으로 업데이트를 트리거하는 시스템입니다.

주요 기능:
1. 프로필 품질 점수 계산
2. 낮은 품질 프로필 식별
3. 자동 업데이트 트리거
4. 모니터링 및 리포팅
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

import numpy as np
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from celery.schedules import crontab

from app.core.celery_worker import celery
from app.core.database import get_async_session
from app.models.user_profile import UserProfile
from app.repositories import (
    UserProfileRepository,
    ChatRepository,
    BookmarkRepository,
    AIProfileRepository
)
from app.services.user_profile_processor import UserProfileProcessor


@dataclass
class ProfileQualityMetrics:
    """프로필 품질 측정 메트릭"""
    user_id: int
    quality_score: float  # 0.0 - 1.0
    completeness_score: float  # 데이터 완성도
    freshness_score: float  # 데이터 최신성
    vector_strength: float  # 벡터 강도
    activity_level: float  # 활동 수준
    last_update_days: int  # 마지막 업데이트 후 경과 일수
    recommendations: List[str]  # 개선 권장사항
    needs_update: bool  # 업데이트 필요 여부


@dataclass
class QualityReport:
    """일일 품질 리포트"""
    date: datetime
    total_profiles: int
    analyzed_profiles: int
    low_quality_profiles: int
    updated_profiles: int
    average_quality: float
    quality_distribution: Dict[str, int]  # 품질 구간별 분포
    update_success_rate: float
    execution_time_seconds: float
    recommendations: List[str]


class ProfileQualityCalculator:
    """프로필 품질 계산기"""

    def __init__(self):
        self.quality_weights = {
            'completeness': 0.3,    # 데이터 완성도
            'freshness': 0.25,      # 데이터 최신성
            'vector_strength': 0.2,  # 벡터 강도
            'activity_level': 0.15,  # 활동 수준
            'diversity': 0.1        # 관심사 다양성
        }

        # 품질 임계값
        self.quality_thresholds = {
            'critical': 0.3,   # 즉시 업데이트 필요
            'low': 0.5,        # 업데이트 권장
            'medium': 0.7,     # 보통
            'high': 0.85       # 우수
        }

    def calculate_profile_quality(self, user_profile: UserProfile) -> ProfileQualityMetrics:
        """사용자 프로필의 품질 점수를 계산합니다."""
        try:
            # 1. 완성도 점수 계산
            completeness_score = self._calculate_completeness_score(user_profile)

            # 2. 최신성 점수 계산
            freshness_score = self._calculate_freshness_score(user_profile)

            # 3. 벡터 강도 점수 계산
            vector_strength_score = self._calculate_vector_strength_score(user_profile)

            # 4. 활동 수준 점수 계산
            activity_score = self._calculate_activity_score(user_profile)

            # 5. 관심사 다양성 점수 계산
            diversity_score = self._calculate_diversity_score(user_profile)

            # 6. 종합 품질 점수 계산
            quality_score = (
                completeness_score * self.quality_weights['completeness'] +
                freshness_score * self.quality_weights['freshness'] +
                vector_strength_score * self.quality_weights['vector_strength'] +
                activity_score * self.quality_weights['activity_level'] +
                diversity_score * self.quality_weights['diversity']
            )

            # 7. 마지막 업데이트 후 경과 일수
            last_update_days = self._calculate_days_since_update(user_profile)

            # 8. 개선 권장사항 생성
            scores = {
                'completeness': completeness_score,
                'freshness': freshness_score,
                'vector_strength': vector_strength_score,
                'activity': activity_score,
                'diversity': diversity_score
            }
            recommendations = self._generate_recommendations(scores, last_update_days)

            # 9. 업데이트 필요 여부 판단
            needs_update = self._determine_update_need(
                quality_score, last_update_days, user_profile
            )

            return ProfileQualityMetrics(
                user_id=user_profile.user_id,
                quality_score=quality_score,
                completeness_score=completeness_score,
                freshness_score=freshness_score,
                vector_strength=user_profile.vector_strength or 0.0,
                activity_level=activity_score,
                last_update_days=last_update_days,
                recommendations=recommendations,
                needs_update=needs_update
            )

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"프로필 품질 계산 실패 - 사용자 {user_profile.user_id}: {e}")
            # 기본값 반환
            return ProfileQualityMetrics(
                user_id=user_profile.user_id,
                quality_score=0.0,
                completeness_score=0.0,
                freshness_score=0.0,
                vector_strength=0.0,
                activity_level=0.0,
                last_update_days=999,
                recommendations=["프로필 품질 계산 오류 - 수동 검토 필요"],
                needs_update=True
            )

    def _calculate_completeness_score(self, profile: UserProfile) -> float:
        """데이터 완성도 점수 계산 (0.0 - 1.0)"""
        score = 0.0
        total_fields = 8

        # 필수 필드들 체크
        if profile.profile_vector and len(profile.profile_vector) > 0:
            score += 1.0  # 가장 중요한 필드
        if profile.keywords_frequency:
            score += 1.0
        if profile.categories_distribution:
            score += 1.0
        if profile.activity_patterns:
            score += 1.0
        if profile.preferences:
            score += 1.0
        if profile.total_bookmarks > 0:
            score += 1.0
        if profile.avg_session_duration is not None:
            score += 1.0
        if profile.completeness_score > 0:
            score += 1.0

        return min(score / total_fields, 1.0)

    def _calculate_freshness_score(self, profile: UserProfile) -> float:
        """데이터 최신성 점수 계산 (0.0 - 1.0)"""
        now = datetime.utcnow()

        # 마지막 업데이트 시간 확인
        last_update = profile.updated_at or profile.created_at
        if not last_update:
            return 0.0

        days_since_update = (now - last_update).days

        # 마지막 활동 시간 확인
        last_activity = profile.last_activity_at
        days_since_activity = 30  # 기본값
        if last_activity:
            days_since_activity = (now - last_activity).days

        # 최신성 점수 계산 (최근일수록 높은 점수)
        update_freshness = max(0.0, 1.0 - (days_since_update / 30.0))  # 30일 기준
        activity_freshness = max(0.0, 1.0 - (days_since_activity / 14.0))  # 14일 기준

        return update_freshness * 0.6 + activity_freshness * 0.4

    def _calculate_vector_strength_score(self, profile: UserProfile) -> float:
        """벡터 강도 점수 계산 (0.0 - 1.0)"""
        if not profile.profile_vector or len(profile.profile_vector) == 0:
            return 0.0

        # 벡터의 L2 노름 계산
        vector_norm = float(np.linalg.norm(profile.profile_vector))

        # 정규화된 강도 점수 (0.5를 기준으로 정규화)
        normalized_strength = min(vector_norm / 0.5, 1.0)

        # 저장된 벡터 강도와 비교
        stored_strength = profile.vector_strength or 0.0

        return max(normalized_strength, stored_strength)

    def _calculate_activity_score(self, profile: UserProfile) -> float:
        """활동 수준 점수 계산 (0.0 - 1.0)"""
        score = 0.0

        # 북마크 수 기반 점수
        bookmark_score = min(profile.total_bookmarks / 50.0, 1.0)  # 50개 기준
        score += bookmark_score * 0.4

        # 세션 시간 기반 점수
        if profile.avg_session_duration:
            session_score = min(profile.avg_session_duration / 30.0, 1.0)  # 30분 기준
            score += session_score * 0.3

        # 최근 활동 기반 점수
        if profile.last_activity_at:
            days_since_activity = (datetime.utcnow() - profile.last_activity_at).days
            activity_score = max(0.0, 1.0 - (days_since_activity / 7.0))  # 7일 기준
            score += activity_score * 0.3

        return min(score, 1.0)

    def _calculate_diversity_score(self, profile: UserProfile) -> float:
        """관심사 다양성 점수 계산 (0.0 - 1.0)"""
        score = 0.0

        # 키워드 다양성
        if profile.keywords_frequency:
            num_keywords = len(profile.keywords_frequency)
            keyword_diversity = min(num_keywords / 20.0, 1.0)  # 20개 기준
            score += keyword_diversity * 0.4

        # 카테고리 다양성
        if profile.categories_distribution:
            num_categories = len(profile.categories_distribution)
            category_diversity = min(num_categories / 10.0, 1.0)  # 10개 기준
            score += category_diversity * 0.6

        return min(score, 1.0)

    def _calculate_days_since_update(self, profile: UserProfile) -> int:
        """마지막 업데이트 후 경과 일수 계산"""
        last_update = profile.updated_at or profile.created_at
        if not last_update:
            return 999  # 매우 오래된 것으로 처리

        return (datetime.utcnow() - last_update).days

    def _generate_recommendations(
        self,
        scores: Dict[str, float],
        days_since_update: int
    ) -> List[str]:
        """개선 권장사항 생성"""
        recommendations = []

        if scores['completeness'] < 0.7:
            recommendations.append("프로필 데이터 완성도 개선 필요")
        if scores['freshness'] < 0.6:
            recommendations.append("프로필 데이터 최신성 업데이트 필요")
        if scores['vector_strength'] < 0.4:
            recommendations.append("관심사 벡터 강화 필요")
        if scores['activity'] < 0.5:
            recommendations.append("사용자 활동 데이터 보강 필요")
        if scores['diversity'] < 0.6:
            recommendations.append("관심사 다양성 확대 필요")
        if days_since_update > 14:
            recommendations.append("장기간 미업데이트 - 우선 업데이트 필요")

        if not recommendations:
            recommendations.append("양호한 프로필 품질 유지 중")

        return recommendations

    def _determine_update_need(
        self,
        quality_score: float,
        days_since_update: int,
        profile: UserProfile
    ) -> bool:
        """업데이트 필요 여부 판단"""
        # 품질 점수가 임계값 이하인 경우
        if quality_score < self.quality_thresholds['low']:
            return True

        # 오래된 프로필인 경우
        if days_since_update > 14:
            return True

        # 벡터가 없는 경우
        if not profile.profile_vector or len(profile.profile_vector) == 0:
            return True

        # 완성도가 매우 낮은 경우
        if profile.completeness_score < 30:
            return True

        return False


class DailyProfileMonitor:
    """일일 프로필 모니터링 시스템"""

    def __init__(self):
        self.quality_calculator = ProfileQualityCalculator()

    async def run_daily_quality_check(self) -> QualityReport:
        """일일 품질 체크 실행"""
        start_time = datetime.utcnow()
        logger.info("🔍 일일 프로필 품질 체크 시작")

        try:
            async for session in get_async_session():
                # 1. 모든 프로필 조회
                profiles = await self._get_all_profiles(session)
                total_profiles = len(profiles)

                if total_profiles == 0:
                    logger.warning("분석할 프로필이 없습니다")
                    return self._generate_empty_report(start_time)

                # 2. 프로필 품질 분석
                quality_metrics = await self._analyze_all_profiles(session, profiles)

                # 3. 낮은 품질 프로필 식별
                low_quality_profiles = [
                    metrics for metrics in quality_metrics
                    if metrics.quality_score <= 0.5
                ]

                # 4. 낮은 품질 프로필 업데이트 트리거
                updated_profiles = await self._trigger_profile_updates(
                    low_quality_profiles
                )

                # 5. 리포트 생성
                report_data = {
                    'start_time': start_time,
                    'total_profiles': total_profiles,
                    'quality_metrics': quality_metrics,
                    'low_quality_count': len(low_quality_profiles),
                    'updated_count': updated_profiles
                }
                report = self._generate_quality_report(report_data)

                logger.info(f"✅ 일일 품질 체크 완료: 총 {total_profiles}개 프로필 중 {len(low_quality_profiles)}개 낮은 품질, {updated_profiles}개 업데이트")
                
                return report

        except Exception as e:
            logger.error(f"일일 품질 체크 실행 중 오류 발생: {e}")
            return self._generate_error_report(start_time, str(e))

    async def _get_all_profiles(self, session: AsyncSession) -> List[UserProfile]:
        """모든 사용자 프로필 조회"""
        try:
            stmt = select(UserProfile).order_by(UserProfile.user_id)
            result = await session.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"프로필 조회 실패: {e}")
            return []

    async def _trigger_profile_updates(
        self,
        low_quality_profiles: List[ProfileQualityMetrics]
    ) -> int:
        """낮은 품질 프로필들의 업데이트 트리거"""
        updated_count = 0

        # Repository들 초기화
        repositories = {
            'chat_repo': ChatRepository(),
            'bookmark_repo': BookmarkRepository(),
            'ai_profile_repo': AIProfileRepository(),
            'user_profile_repo': UserProfileRepository()
        }

        # 프로필 프로세서 초기화
        processor = UserProfileProcessor(repositories)

        for metrics in low_quality_profiles:
            try:
                logger.info(
                    f"🔄 사용자 {metrics.user_id} 프로필 업데이트 트리거 "
                    f"(품질 점수: {metrics.quality_score:.3f})"
                )

                # 프로필 업데이트 실행
                success = await self._update_single_profile(
                    metrics.user_id, processor
                )

                if success:
                    updated_count += 1

            except (AttributeError, ValueError, TypeError) as e:
                logger.error(f"사용자 {metrics.user_id} 업데이트 실패: {e}")
                continue

        return updated_count

    async def _update_single_profile(
        self,
        user_id: int,
        processor: UserProfileProcessor
    ) -> bool:
        """단일 프로필 업데이트 수행"""
        try:
            # 프로필 업데이트 실행
            result = await processor.update_user_profile(
                user_id=user_id,
                force_full_recalculation=False,  # 증분 업데이트 우선
                include_historical_data=True
            )

            # 결과 확인
            if result.get('error'):
                logger.error(f"사용자 {user_id} 프로필 업데이트 실패: {result['error']}")
                return False

            logger.info(f"✅ 사용자 {user_id} 프로필 업데이트 완료")
            return True

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"사용자 {user_id} 프로필 업데이트 실패: {e}")
            return False

    def _generate_quality_report(
        self,
        report_data: dict
    ) -> QualityReport:
        """품질 리포트 생성"""
        start_time = report_data['start_time']
        total_profiles = report_data['total_profiles']
        quality_metrics = report_data['quality_metrics']
        low_quality_count = report_data['low_quality_count']
        updated_count = report_data['updated_count']

        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()

        # 평균 품질 계산
        if quality_metrics:
            average_quality = sum(m.quality_score for m in quality_metrics) / len(quality_metrics)
        else:
            average_quality = 0.0

        # 품질 분포 계산
        quality_distribution = {
            'critical': 0,  # < 0.3
            'low': 0,       # 0.3 - 0.5
            'medium': 0,    # 0.5 - 0.7
            'good': 0,      # 0.7 - 0.85
            'excellent': 0  # > 0.85
        }

        for metrics in quality_metrics:
            score = metrics.quality_score
            if score < 0.3:
                quality_distribution['critical'] += 1
            elif score < 0.5:
                quality_distribution['low'] += 1
            elif score < 0.7:
                quality_distribution['medium'] += 1
            elif score < 0.85:
                quality_distribution['good'] += 1
            else:
                quality_distribution['excellent'] += 1

        # 업데이트 성공률 계산
        update_success_rate = (updated_count / low_quality_count) if low_quality_count > 0 else 1.0

        # 개선 권장사항 생성
        recommendations = []
        for metrics in quality_metrics:
            recommendations.extend(metrics.recommendations)

        return QualityReport(
            date=start_time.date(),
            total_profiles=total_profiles,
            analyzed_profiles=len(quality_metrics),
            low_quality_profiles=low_quality_count,
            updated_profiles=updated_count,
            average_quality=average_quality,
            quality_distribution=quality_distribution,
            update_success_rate=update_success_rate,
            execution_time_seconds=execution_time,
            recommendations=recommendations
        )

    async def _analyze_all_profiles(
        self, 
        session: AsyncSession, 
        profiles: List[UserProfile]
    ) -> List[ProfileQualityMetrics]:
        """모든 프로필의 품질을 분석합니다."""
        quality_metrics = []
        
        for profile in profiles:
            try:
                metrics = self.quality_calculator.calculate_profile_quality(profile)
                quality_metrics.append(metrics)
                
            except (AttributeError, ValueError, TypeError) as e:
                logger.error(f"프로필 {profile.user_id} 품질 분석 실패: {e}")
                continue
        
        logger.info(f"📊 총 {len(profiles)}개 프로필 중 {len(quality_metrics)}개 분석 완료")
        return quality_metrics

    def _generate_empty_report(self, start_time: datetime) -> QualityReport:
        """빈 리포트 생성"""
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        return QualityReport(
            date=datetime.utcnow().date(),
            total_profiles=0,
            analyzed_profiles=0,
            low_quality_profiles=0,
            updated_profiles=0,
            average_quality=0.0,
            quality_distribution={
                'critical': 0, 'low': 0, 'medium': 0, 'good': 0, 'excellent': 0
            },
            update_success_rate=0.0,
            execution_time_seconds=execution_time,
            recommendations=["분석할 프로필이 없습니다"]
        )

    def _generate_error_report(self, start_time: datetime, error_msg: str) -> QualityReport:
        """오류 리포트 생성"""
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        
        return QualityReport(
            date=datetime.utcnow().date(),
            total_profiles=0,
            analyzed_profiles=0,
            low_quality_profiles=0,
            updated_profiles=0,
            average_quality=0.0,
            quality_distribution={
                'critical': 0, 'low': 0, 'medium': 0, 'good': 0, 'excellent': 0
            },
            update_success_rate=0.0,
            execution_time_seconds=execution_time,
            recommendations=[f"오류로 인한 분석 실패: {error_msg}"]
        )


# Celery 작업 정의
@celery.task(
    name="tasks.run_daily_quality_check",
    bind=False,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 300},
    retry_backoff=True,
    retry_jitter=True,
)
def run_daily_quality_check_task() -> dict:
    """
    일일 프로필 품질 체크 Celery 작업

    Returns:
        dict: 실행 결과 요약
    """
    async def _async_quality_check():
        try:
            monitor = DailyProfileMonitor()
            report = await monitor.run_daily_quality_check()

            return {
                "success": True,
                "date": report.date.isoformat(),
                "total_profiles": report.total_profiles,
                "analyzed_profiles": report.analyzed_profiles,
                "low_quality_profiles": report.low_quality_profiles,
                "updated_profiles": report.updated_profiles,
                "average_quality": report.average_quality,
                "quality_distribution": report.quality_distribution,
                "update_success_rate": report.update_success_rate,
                "execution_time_seconds": report.execution_time_seconds,
                "recommendations": report.recommendations
            }

        except Exception as e:
            logger.error(f"일일 품질 체크 실행 중 오류 발생: {e}")
            return {
                "success": False,
                "error": str(e),
                "date": datetime.utcnow().date().isoformat(),
                "total_profiles": 0,
                "analyzed_profiles": 0,
                "low_quality_profiles": 0,
                "updated_profiles": 0,
                "average_quality": 0.0,
                "quality_distribution": {},
                "update_success_rate": 0.0,
                "execution_time_seconds": 0.0
            }

    # 이벤트 루프 처리
    try:
        # 현재 실행 중인 이벤트 루프가 있는지 확인
        loop = asyncio.get_running_loop()
        # 이미 실행 중인 경우, 새 스레드에서 실행
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, _async_quality_check())
            return future.result()
    except RuntimeError:
        # 실행 중인 루프가 없는 경우, 새 루프 생성
        return asyncio.run(_async_quality_check())


# 편의 함수들
async def calculate_single_profile_quality(user_id: int) -> Optional[ProfileQualityMetrics]:
    """단일 프로필의 품질 계산"""
    calculator = ProfileQualityCalculator()
    
    async for session in get_async_session():
        try:
            # UserProfile 직접 조회
            from sqlalchemy import select
            stmt = select(UserProfile).where(UserProfile.user_id == user_id)
            result = await session.execute(stmt)
            profile = result.scalar_one_or_none()
            
            if not profile:
                logger.warning(f"사용자 ID {user_id}의 프로필을 찾을 수 없습니다")
                return None
            
            # 품질 계산
            quality_metrics = calculator.calculate_profile_quality(profile)
            return quality_metrics
            
        except Exception as e:
            logger.error(f"사용자 ID {user_id} 프로필 품질 계산 실패: {e}")
            return None
        
        break  # async for는 한 번만 실행


async def get_low_quality_profiles(threshold: float = 0.5) -> List[ProfileQualityMetrics]:
    """낮은 품질의 프로필 목록 조회"""
    monitor = DailyProfileMonitor()

    async for session in get_async_session():
        try:
            profiles = await monitor._get_all_profiles(session)
            quality_metrics = await monitor._analyze_all_profiles(session, profiles)
            
            # 임계값 이하의 프로필들 필터링
            low_quality = [
                metrics for metrics in quality_metrics
                if metrics.quality_score <= threshold
            ]
            
            return low_quality
            
        except Exception as e:
            logger.error(f"낮은 품질 프로필 조회 실패: {e}")
            return []
        
        break  # async for는 한 번만 실행


# Celery Beat 스케줄링 설정을 위한 유틸리티 함수
def setup_daily_monitoring_schedule():
    """
    Celery Beat 스케줄링 설정을 위한 함수

    이 함수는 celery.py 또는 설정 파일에서 호출되어야 합니다:

    CELERY_BEAT_SCHEDULE = {
        'daily-profile-quality-check': {
            'task': 'tasks.run_daily_quality_check',
            'schedule': crontab(hour=2, minute=0),  # 매일 오전 2시
        },
    }
    """
    return {
        'daily-profile-quality-check': {
            'task': 'tasks.run_daily_quality_check',
            'schedule': crontab(hour=2, minute=0),  # 매일 오전 2시
            'options': {
                'expires': 60 * 60 * 8,  # 8시간 후 만료
                'queue': 'quality_check'  # 전용 큐 사용
            }
        }
    }
