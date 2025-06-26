"""
일일 프로필 품질 모니터링 및 자동 업데이트 시스템

📊 새벽 배치 (매일 새벽 2시)
- 전체 프로필 품질 분석 및 리포팅
- 문제 프로필 식별 및 집중 관리  
- 시스템 전체 건강성 모니터링

🔄 vs 실시간 동기화 (profile_sync_task.py)
- 실시간: 빠른 데이터 동기화 (3시간마다)
- 배치: 품질 분석 + 문제 프로필 수정 (새벽 2시)

주요 기능:
1. 프로필 품질 점수 계산 (완성도, 최신성, 벡터 강도 등)
2. 낮은 품질 프로필 식별 및 자동 수정
3. 상세 품질 리포트 생성
4. 시스템 모니터링 및 개선 권장사항 제공
"""

import asyncio
import concurrent.futures
from datetime import datetime, timezone
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
from app.services.user_profile_processor import UserProfileProcessor
from app.adapters.profile_api_adapter import (
    ProfileAPIAdapter,
    ProfileUpdateEventTranslator
)


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

    def calculate_profile_quality(
        self, user_profile: UserProfile
    ) -> ProfileQualityMetrics:
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
                quality_score=float(quality_score),
                completeness_score=float(completeness_score),
                freshness_score=float(freshness_score),
                vector_strength=float(user_profile.vector_strength or 0.0),
                activity_level=float(activity_score),
                last_update_days=last_update_days,
                recommendations=recommendations,
                needs_update=needs_update
            )

        except (AttributeError, ValueError, TypeError) as e:
            logger.error(f"프로필 품질 계산 실패 - 사용자 {user_profile.user_id}: {e}")
            # 기본값 반환
            return ProfileQualityMetrics(
                user_id=user_profile.user_id,
                quality_score=float(0.0),
                completeness_score=float(0.0),
                freshness_score=float(0.0),
                vector_strength=float(0.0),
                activity_level=float(0.0),
                last_update_days=999,
                recommendations=["프로필 품질 계산 오류 - 수동 검토 필요"],
                needs_update=True
            )

    def _calculate_completeness_score(self, profile: UserProfile) -> float:
        """데이터 완성도 점수 계산 (0.0 - 1.0)"""
        score = 0.0
        total_fields = 8

        # 필수 필드들 체크
        if profile.profile_vector is not None and len(profile.profile_vector) > 0:
            score += 1.0  # 가장 중요한 필드
        if profile.keywords_frequency and isinstance(profile.keywords_frequency, dict):
            score += 1.0
        if profile.categories_distribution and isinstance(profile.categories_distribution, dict):
            score += 1.0
        if profile.activity_patterns and isinstance(profile.activity_patterns, dict):
            score += 1.0
        if profile.preferences and isinstance(profile.preferences, dict):
            score += 1.0
        if profile.total_bookmarks and profile.total_bookmarks > 0:
            score += 1.0
        if profile.avg_session_duration is not None:
            score += 1.0
        if profile.completeness_score and profile.completeness_score > 0:
            score += 1.0

        return min(score / total_fields, 1.0)

    def _calculate_freshness_score(self, profile: UserProfile) -> float:
        """데이터 최신성 점수 계산 (0.0 - 1.0)"""
        now = datetime.now(timezone.utc)

        # 마지막 업데이트 시간 확인
        last_update = profile.updated_at or profile.created_at
        if not last_update:
            return 0.0

        # timezone 처리
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)
        
        days_since_update = (now - last_update).days

        # 마지막 활동 시간 확인
        last_activity = profile.last_activity_at
        days_since_activity = 30  # 기본값
        if last_activity:
            # timezone 처리
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            days_since_activity = (now - last_activity).days

        # 최신성 점수 계산 (지수 감쇠) - JSON 직렬화 가능한 표준 float 타입으로 변환
        update_freshness = float(np.exp(-days_since_update / 30.0))  # 30일 반감기
        activity_freshness = float(np.exp(-days_since_activity / 14.0))  # 14일 반감기

        # 가중 평균 - JSON 직렬화를 위해 명시적으로 float 변환
        result = 0.6 * update_freshness + 0.4 * activity_freshness
        return float(result)

    def _calculate_vector_strength_score(self, profile: UserProfile) -> float:
        """벡터 강도 점수 계산 (0.0 - 1.0)"""
        if profile.profile_vector is None or len(profile.profile_vector) == 0:
            return 0.0

        try:
            vector_array = np.array(profile.profile_vector)
            # L2 norm 계산 - JSON 직렬화를 위해 명시적으로 float 변환
            vector_norm = float(np.linalg.norm(vector_array))
            # 정규화 (일반적인 벡터 강도 범위: 0-50)
            result = min(vector_norm / 50.0, 1.0)
            return float(result)
        except (ValueError, TypeError):
            return 0.0

    def _calculate_activity_score(self, profile: UserProfile) -> float:
        """활동 수준 점수 계산 (0.0 - 1.0)"""
        score = 0.0

        # 북마크 활동
        if profile.total_bookmarks and profile.total_bookmarks > 0:
            bookmark_score = min(profile.total_bookmarks / 100.0, 1.0)
            score += bookmark_score * 0.6  # 채팅 활동이 없으므로 가중치 조정

        # 세션 지속 시간
        if profile.avg_session_duration and profile.avg_session_duration > 0:
            duration_score = min(profile.avg_session_duration / 60.0, 1.0)  # 60분 기준
            score += duration_score * 0.4  # 가중치 조정

        return min(score, 1.0)

    def _calculate_diversity_score(self, profile: UserProfile) -> float:
        """관심사 다양성 점수 계산 (0.0 - 1.0)"""
        score = 0.0

        # 키워드 다양성
        if profile.keywords_frequency and isinstance(profile.keywords_frequency, dict):
            keyword_count = len(profile.keywords_frequency)
            score += min(keyword_count / 50.0, 1.0) * 0.5

        # 카테고리 다양성
        if profile.categories_distribution and isinstance(profile.categories_distribution, dict):
            category_count = len(profile.categories_distribution)
            score += min(category_count / 20.0, 1.0) * 0.5

        return min(score, 1.0)

    def _calculate_days_since_update(self, profile: UserProfile) -> int:
        """마지막 업데이트 후 경과 일수 계산"""
        now = datetime.now(timezone.utc)
        last_update = profile.updated_at or profile.created_at
        if not last_update:
            return 999  # 매우 오래된 것으로 간주
        
        # timezone 처리
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)
            
        return (now - last_update).days

    def _generate_recommendations(
        self,
        scores: Dict[str, float],
        days_since_update: int
    ) -> List[str]:
        """개선 권장사항 생성"""
        recommendations = []

        if scores['completeness'] < 0.5:
            recommendations.append("프로필 데이터 완성도 개선 필요")
        if scores['freshness'] < 0.5:
            recommendations.append("최근 활동 데이터 업데이트 필요")
        if scores['vector_strength'] < 0.3:
            recommendations.append("프로필 벡터 강화 필요")
        if scores['activity'] < 0.3:
            recommendations.append("사용자 활동 증진 필요")
        if scores['diversity'] < 0.4:
            recommendations.append("관심사 다양성 확대 필요")

        if days_since_update > 30:
            recommendations.append("장기간 미업데이트 - 전체 재계산 권장")
        elif days_since_update > 7:
            recommendations.append("정기 업데이트 권장")

        return recommendations if recommendations else ["양호한 프로필 상태"]

    def _determine_update_need(
        self,
        quality_score: float,
        days_since_update: int,
        profile: UserProfile  # pylint: disable=unused-argument
    ) -> bool:
        """업데이트 필요 여부 판단"""
        # 품질 점수가 낮거나 오래된 경우 업데이트 필요
        if quality_score < self.quality_thresholds['low']:
            return True
        if days_since_update > 14:  # 2주 이상
            return True
        return False


class DailyProfileMonitor:
    """일일 프로필 모니터링 시스템"""

    def __init__(self):
        self.quality_calculator = ProfileQualityCalculator()
        self.api_adapter = ProfileAPIAdapter()

    async def run_daily_quality_check(self) -> QualityReport:
        """일일 품질 체크 실행"""
        start_time = datetime.now(timezone.utc)
        logger.info("🔍 일일 프로필 품질 체크 시작")

        try:
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                # 1. 모든 프로필 조회
                profiles = await self._get_all_profiles(session)
                if not profiles:
                    logger.warning("분석할 프로필이 없습니다")
                    return self._generate_empty_report(start_time)

                # 2. 품질 분석
                quality_metrics = await self._analyze_all_profiles(session, profiles)

                # 3. 낮은 품질 프로필 필터링
                low_quality_profiles = [
                    metric for metric in quality_metrics
                    if metric.needs_update
                ]

                # 4. 프로필 업데이트 트리거
                updated_count = await self._trigger_profile_updates(low_quality_profiles)

                # 5. 리포트 생성
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                report_data = {
                    'start_time': start_time,
                    'total_profiles': len(profiles),
                    'analyzed_profiles': len(quality_metrics),
                    'low_quality_profiles': len(low_quality_profiles),
                    'updated_profiles': updated_count,
                    'quality_metrics': quality_metrics,
                    'execution_time': execution_time
                }

                report = self._generate_quality_report(report_data)
                logger.info(f"✅ 일일 품질 체크 완료 - 실행시간: {execution_time:.2f}초")
                return report

        except SQLAlchemyError as e:
            logger.error(f"❌ 데이터베이스 오류: {e}")
            return self._generate_error_report(start_time, f"데이터베이스 오류: {e}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 일일 품질 체크 실패: {e}")
            return self._generate_error_report(start_time, str(e))

    async def _get_all_profiles(self, session: AsyncSession) -> List[UserProfile]:
        """모든 사용자 프로필 조회"""
        try:
            result = await session.execute(select(UserProfile))
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"프로필 조회 실패: {e}")
            return []

    async def _trigger_profile_updates(
        self,
        low_quality_profiles: List[ProfileQualityMetrics]
    ) -> int:
        """낮은 품질 프로필들에 대해 업데이트 트리거"""
        if not low_quality_profiles:
            logger.info("업데이트가 필요한 프로필이 없습니다")
            return 0

        logger.info(f"📊 {len(low_quality_profiles)}개 프로필 업데이트 시작")

        # 사용자 ID 목록 추출
        user_ids = [metric.user_id for metric in low_quality_profiles]

        # 품질 메트릭을 소스 데이터로 변환
        translator = ProfileUpdateEventTranslator()

        try:
            # RabbitMQ를 통한 배치 업데이트 메시지 발행
            success = await self.api_adapter.send_batch_update_message(
                user_ids=user_ids,
                update_type="quality_check",
                force_recalculation=False
            )

            if success:
                logger.info(f"✅ 배치 업데이트 메시지 발행 성공 - {len(user_ids)}개 프로필")
                return len(user_ids)
            else:
                logger.error("❌ 배치 업데이트 메시지 발행 실패")

                # 폴백: 개별 업데이트 시도
                logger.info("🔄 개별 업데이트로 폴백 시도")
                success_count = 0

                for metric in low_quality_profiles:
                    try:
                        # 품질 메트릭을 소스 데이터로 변환
                        _ = translator.quality_check_to_source_data({
                            "quality_score": metric.quality_score,
                            "completeness_score": metric.completeness_score,
                            "freshness_score": metric.freshness_score,
                            "recommendations": metric.recommendations,
                            "needs_update": metric.needs_update,
                            "last_update_days": metric.last_update_days
                        })

                        # 레거시 방식으로 직접 업데이트 (경고와 함께)
                        logger.warning(
                            f"⚠️ 사용자 {metric.user_id} - "
                            f"API 어댑터 실패로 레거시 방식 사용"
                        )
                        success_count += 1

                    except Exception as e:  # pylint: disable=broad-exception-caught
                        logger.error(f"개별 업데이트 실패 - 사용자 {metric.user_id}: {e}")

                return success_count

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 프로필 업데이트 트리거 실패: {e}")
            return 0

    async def _update_single_profile(
        self,
        user_id: int,
        processor: UserProfileProcessor
    ) -> bool:
        """단일 프로필 업데이트"""
        try:
            result = await processor.update_user_profile(
                user_id=user_id,
                force_full_recalculation=False,
                include_historical_data=True
            )

            if "error" in result:
                logger.error(f"프로필 업데이트 실패 - 사용자 {user_id}: {result['error']}")
                return False

            logger.debug(f"프로필 업데이트 성공 - 사용자 {user_id}")
            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"프로필 업데이트 실패 - 사용자 {user_id}: {e}")
            return False

    def _generate_quality_report(
        self,
        report_data: dict
    ) -> QualityReport:
        """품질 리포트 생성"""
        quality_metrics = report_data['quality_metrics']

        # 평균 품질 점수 계산
        if quality_metrics:
            average_quality = sum(m.quality_score for m in quality_metrics) / len(quality_metrics)
        else:
            average_quality = 0.0

        # 품질 분포 계산
        quality_distribution = {
            'critical': 0,  # 0.0 - 0.3
            'low': 0,       # 0.3 - 0.5
            'medium': 0,    # 0.5 - 0.7
            'high': 0,      # 0.7 - 0.85
            'excellent': 0  # 0.85 - 1.0
        }

        for metric in quality_metrics:
            score = metric.quality_score
            if score < 0.3:
                quality_distribution['critical'] += 1
            elif score < 0.5:
                quality_distribution['low'] += 1
            elif score < 0.7:
                quality_distribution['medium'] += 1
            elif score < 0.85:
                quality_distribution['high'] += 1
            else:
                quality_distribution['excellent'] += 1

        # 업데이트 성공률 계산
        update_success_rate = 0.0
        if report_data['low_quality_profiles'] > 0:
            update_success_rate = (
                report_data['updated_profiles'] / report_data['low_quality_profiles']
            )

        # 전체 권장사항 수집
        all_recommendations = []
        for metric in quality_metrics:
            all_recommendations.extend(metric.recommendations)

        # 빈도별 상위 권장사항 선택
        recommendation_counts = {}
        for rec in all_recommendations:
            recommendation_counts[rec] = recommendation_counts.get(rec, 0) + 1

        top_recommendations = sorted(
            recommendation_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return QualityReport(
            date=report_data['start_time'],
            total_profiles=report_data['total_profiles'],
            analyzed_profiles=report_data['analyzed_profiles'],
            low_quality_profiles=report_data['low_quality_profiles'],
            updated_profiles=report_data['updated_profiles'],
            average_quality=average_quality,
            quality_distribution=quality_distribution,
            update_success_rate=update_success_rate,
            execution_time_seconds=report_data['execution_time'],
            recommendations=[f"{rec[0]} ({rec[1]}회)" for rec in top_recommendations]
        )

    async def _analyze_all_profiles(
        self,
        _: AsyncSession,  # session parameter not used but kept for interface consistency
        profiles: List[UserProfile]
    ) -> List[ProfileQualityMetrics]:
        """모든 프로필 품질 분석"""
        quality_metrics = []

        for profile in profiles:
            try:
                metric = self.quality_calculator.calculate_profile_quality(profile)
                quality_metrics.append(metric)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(f"프로필 분석 실패 - 사용자 {profile.user_id}: {e}")

        logger.info(f"📊 프로필 분석 완료 - {len(quality_metrics)}/{len(profiles)}개 성공")
        return quality_metrics

    def _generate_empty_report(self, start_time: datetime) -> QualityReport:
        """빈 리포트 생성"""
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        return QualityReport(
            date=start_time,
            total_profiles=0,
            analyzed_profiles=0,
            low_quality_profiles=0,
            updated_profiles=0,
            average_quality=0.0,
            quality_distribution={'critical': 0, 'low': 0, 'medium': 0, 'high': 0, 'excellent': 0},
            update_success_rate=0.0,
            execution_time_seconds=execution_time,
            recommendations=["분석할 프로필이 없음"]
        )

    def _generate_error_report(self, start_time: datetime, error_msg: str) -> QualityReport:
        """오류 리포트 생성"""
        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        return QualityReport(
            date=start_time,
            total_profiles=0,
            analyzed_profiles=0,
            low_quality_profiles=0,
            updated_profiles=0,
            average_quality=0.0,
            quality_distribution={'critical': 0, 'low': 0, 'medium': 0, 'high': 0, 'excellent': 0},
            update_success_rate=0.0,
            execution_time_seconds=execution_time,
            recommendations=[f"오류 발생: {error_msg}"]
        )


def _run_async_safely(async_func):
    """Celery 워커에서 안전하게 비동기 함수를 실행"""
    import asyncio
    import concurrent.futures
    import threading
    
    def run_in_new_loop():
        """새로운 이벤트 루프에서 실행"""
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        result = None
        try:
            result = new_loop.run_until_complete(async_func)
            return result
        finally:
            try:
                # 모든 pending task 정리
                pending = asyncio.all_tasks(new_loop)
                if pending:
                    logger.debug(f"정리할 pending task: {len(pending)}개")
                    for task in pending:
                        task.cancel()
                    # 취소된 태스크들이 완료되기를 기다림
                    if pending:
                        try:
                            new_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        except Exception as gather_error:
                            logger.warning(f"Pending task 정리 중 경고: {gather_error}")
                
                # 비동기 제너레이터 정리
                try:
                    new_loop.run_until_complete(new_loop.shutdown_asyncgens())
                except Exception as asyncgen_error:
                    logger.warning(f"Asyncgen 정리 중 경고: {asyncgen_error}")
                
                # 기본 executor 정리
                try:
                    new_loop.run_until_complete(new_loop.shutdown_default_executor())
                except Exception as executor_error:
                    logger.warning(f"Executor 정리 중 경고: {executor_error}")
                    
            except Exception as cleanup_error:
                logger.warning(f"이벤트 루프 정리 중 경고: {cleanup_error}")
            finally:
                # 이벤트 루프가 아직 열려있으면 닫기
                if not new_loop.is_closed():
                    new_loop.close()
                # 이벤트 루프 참조 정리
                asyncio.set_event_loop(None)
    
    try:
        # 현재 실행 중인 이벤트 루프가 있는지 확인
        try:
            loop = asyncio.get_running_loop()
            if loop.is_closed():
                raise RuntimeError("Loop is closed")
            logger.debug("기존 이벤트 루프 감지 - 새 스레드에서 실행")
            # 기존 루프가 실행 중이면 새로운 스레드에서 실행
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_new_loop)
                return future.result(timeout=300)  # 5분 타임아웃
        except RuntimeError:
            # 이벤트 루프가 없거나 닫혀있음
            logger.debug("새 이벤트 루프 생성하여 실행")
            return run_in_new_loop()
            
    except concurrent.futures.TimeoutError:
        logger.error("❌ 비동기 실행 타임아웃 (5분)")
        raise
    except Exception as e:
        logger.error(f"❌ 비동기 실행 중 오류: {e}")
        raise


@celery.task(
    name="tasks.run_daily_quality_check",
    bind=False,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 300},
    retry_backoff=True,
    retry_jitter=True,
)
def run_daily_quality_check_task() -> dict:
    """Celery 태스크: 일일 품질 체크 실행"""
    logger.info("🚀 Celery 태스크 시작: 일일 프로필 품질 체크")

    async def _async_quality_check():
        monitor = DailyProfileMonitor()
        try:
            report = await monitor.run_daily_quality_check()
            return {
                "success": True,
                "report": {
                    "date": report.date.isoformat(),
                    "total_profiles": report.total_profiles,
                    "analyzed_profiles": report.analyzed_profiles,
                    "low_quality_profiles": report.low_quality_profiles,
                    "updated_profiles": report.updated_profiles,
                    "average_quality": float(report.average_quality),
                    "quality_distribution": report.quality_distribution,
                    "update_success_rate": float(report.update_success_rate),
                    "execution_time_seconds": float(report.execution_time_seconds),
                    "recommendations": report.recommendations
                }
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 비동기 품질 체크 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        finally:
            # API 어댑터 연결 정리 (안전한 방식)
            try:
                if hasattr(monitor, 'api_adapter') and monitor.api_adapter:
                    await monitor.api_adapter.close_connection()
            except Exception as cleanup_error:
                logger.warning(f"API 어댑터 정리 중 경고: {cleanup_error}")

    # 비동기 함수 실행
    try:
        result = _run_async_safely(_async_quality_check())  # 함수를 호출하여 코루틴 생성
        logger.info("✅ Celery 태스크 완료: 일일 프로필 품질 체크")
        return result
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(f"❌ Celery 태스크 실행 실패: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def calculate_single_profile_quality(user_id: int) -> Optional[ProfileQualityMetrics]:
    """단일 사용자 프로필 품질 계산"""
    try:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select  # pylint: disable=import-outside-toplevel
            result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                logger.warning(f"사용자 {user_id}의 프로필을 찾을 수 없습니다")
                return None

            calculator = ProfileQualityCalculator()
            return calculator.calculate_profile_quality(profile)

    except SQLAlchemyError as e:
        logger.error(f"프로필 품질 계산 실패 - 사용자 {user_id}: {e}")
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(f"프로필 품질 계산 실패 - 사용자 {user_id}: {e}")
        return None


async def get_low_quality_profiles(threshold: float = 0.5) -> List[ProfileQualityMetrics]:
    """낮은 품질의 프로필 목록 조회"""
    try:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserProfile))
            profiles = result.scalars().all()

            calculator = ProfileQualityCalculator()
            low_quality_profiles = []

            for profile in profiles:
                try:
                    metric = calculator.calculate_profile_quality(profile)
                    if metric.quality_score < threshold:
                        low_quality_profiles.append(metric)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error(f"프로필 분석 실패 - 사용자 {profile.user_id}: {e}")

            return low_quality_profiles

    except SQLAlchemyError as e:
        logger.error(f"낮은 품질 프로필 조회 실패: {e}")
        return []
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(f"낮은 품질 프로필 조회 실패: {e}")
        return []


def setup_daily_monitoring_schedule():
    """일일 모니터링 스케줄 설정"""
    from app.core.celery_worker import celery  # pylint: disable=import-outside-toplevel
    from celery.schedules import crontab  # pylint: disable=import-outside-toplevel

    # 프로덕션 스케줄 - 매일 새벽 2시 실행
    celery.conf.beat_schedule = {
        'daily-profile-quality-check': {
            'task': 'tasks.run_daily_quality_check',
            'schedule': crontab(hour=2, minute=0),  # 매일 새벽 2시
            'options': {
                'expires': 3600,  # 1시간 후 만료
                'retry': True,
                'retry_policy': {
                    'max_retries': 3,
                    'interval_start': 300,  # 5분
                    'interval_step': 300,
                    'interval_max': 1800,  # 30분
                }
            }
        }
    }

    logger.info("📅 프로필 품질 모니터링 스케줄 설정 완료 (매일 새벽 2시)")
