"""
추천 피드백 시스템

사용자의 추천 상호작용을 추적하고 분석하여
추천 시스템의 성능을 지속적으로 개선하는 서비스입니다.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, and_, desc, func, text

from app.core.database import get_async_session
from app.models.user_profile import (
    Recommendation, RecommendationCreate, RecommendationUpdate,
    UserProfile, ContextualRecommendation, ContextualRecommendationCreate
)

log = logging.getLogger(__name__)


class RecommendationFeedbackService:
    """추천 피드백 수집 및 분석 서비스"""

    def __init__(self):
        self.feedback_weights = {
            'clicked': 0.3,
            'saved': 1.0,
            'shared': 0.8,
            'dismissed': -0.5,
            'ignored': -0.1
        }

    async def record_recommendation_shown(
        self,
        user_id: int,
        recommendation_data: Dict[str, Any],
        recommendation_type: str = "general",
        session_id: Optional[str] = None
    ) -> Optional[UUID]:
        """
        사용자에게 추천이 표시되었음을 기록합니다.

        Args:
            user_id: 사용자 ID
            recommendation_data: 추천 데이터 (URL, 점수, 이유 등)
            recommendation_type: 추천 타입 (general, search_based 등)
            session_id: 세션 ID (컨텍스트 추천용)

        Returns:
            추천 기록 ID
        """
        try:
            async for session in get_async_session():
                # 기본 추천 기록 생성
                recommendation = Recommendation(
                    user_id=user_id,
                    recommended_url=recommendation_data.get('url', ''),
                    recommendation_score=recommendation_data.get('recommendation_score', 0.0),
                    recommendation_type=recommendation_type,
                    reasoning=recommendation_data.get('reasoning', {}),
                    shown_at=datetime.utcnow()
                )

                session.add(recommendation)
                await session.commit()
                await session.refresh(recommendation)

                # 컨텍스트 추천인 경우 추가 기록
                if session_id and recommendation_data.get('trigger_bookmark_id'):
                    contextual_rec = ContextualRecommendation(
                        user_id=user_id,
                        session_id=session_id,
                        trigger_bookmark_id=recommendation_data['trigger_bookmark_id'],
                        recommended_bookmark_id=recommendation_data.get('source_id', ''),
                        context_type=recommendation_type,
                        relevance_score=recommendation_data.get('recommendation_score', 0.0),
                        context_factors=recommendation_data.get('reasoning', {}),
                        shown_at=datetime.utcnow()
                    )
                    session.add(contextual_rec)
                    await session.commit()

                log.info(f"추천 표시 기록 - 사용자: {user_id}, 타입: {recommendation_type}")
                return recommendation.id

        except Exception as e:
            log.error(f"추천 표시 기록 오류: {e}")
            return None

    async def record_user_action(
        self,
        recommendation_id: UUID,
        action: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        추천에 대한 사용자 액션을 기록합니다.

        Args:
            recommendation_id: 추천 기록 ID
            action: 사용자 액션 (clicked, saved, dismissed, ignored 등)
            additional_data: 추가 액션 데이터

        Returns:
            기록 성공 여부
        """
        try:
            async for session in get_async_session():
                # 추천 기록 업데이트
                recommendation = await session.get(Recommendation, recommendation_id)
                if not recommendation:
                    log.warning(f"추천 기록을 찾을 수 없음: {recommendation_id}")
                    return False

                recommendation.user_action = action
                recommendation.action_at = datetime.utcnow()

                if additional_data:
                    current_reasoning = recommendation.reasoning or {}
                    current_reasoning.update(additional_data)
                    recommendation.reasoning = current_reasoning

                await session.commit()

                # 사용자 프로파일 업데이트를 위한 피드백 처리
                await self._process_feedback_for_profile_update(
                    session, recommendation, action
                )

                log.info(f"사용자 액션 기록 - 추천: {recommendation_id}, 액션: {action}")
                return True

        except Exception as e:
            log.error(f"사용자 액션 기록 오류: {e}")
            return False

    async def get_recommendation_performance_stats(
        self,
        user_id: Optional[int] = None,
        recommendation_type: Optional[str] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        추천 시스템 성능 통계를 조회합니다.

        Args:
            user_id: 특정 사용자 (None이면 전체)
            recommendation_type: 특정 추천 타입
            days_back: 분석 기간 (일)

        Returns:
            성능 통계 데이터
        """
        try:
            async for session in get_async_session():
                cutoff_date = datetime.utcnow() - timedelta(days=days_back)

                # 기본 쿼리 조건
                conditions = [Recommendation.shown_at >= cutoff_date]
                if user_id:
                    conditions.append(Recommendation.user_id == user_id)
                if recommendation_type:
                    conditions.append(Recommendation.recommendation_type == recommendation_type)

                # 전체 추천 수
                total_query = select(func.count(Recommendation.id)).where(and_(*conditions))
                total_result = await session.execute(total_query)
                total_recommendations = total_result.scalar() or 0

                # 액션별 통계
                action_stats = {}
                for action in ['clicked', 'saved', 'dismissed', 'ignored']:
                    action_conditions = conditions + [Recommendation.user_action == action]
                    action_query = select(func.count(Recommendation.id)).where(and_(*action_conditions))
                    action_result = await session.execute(action_query)
                    action_count = action_result.scalar() or 0
                    action_stats[action] = {
                        'count': action_count,
                        'rate': action_count / total_recommendations if total_recommendations > 0 else 0
                    }

                # 추천 타입별 성능
                type_stats_query = select(
                    Recommendation.recommendation_type,
                    func.count(Recommendation.id).label('total'),
                    func.count(Recommendation.user_action).label('with_action'),
                    func.sum(
                        func.case(
                            (Recommendation.user_action == 'saved', 1),
                            else_=0
                        )
                    ).label('saved_count')
                ).where(and_(*conditions)).group_by(Recommendation.recommendation_type)

                type_result = await session.execute(type_stats_query)
                type_stats = {}
                for row in type_result.fetchall():
                    type_stats[row.recommendation_type] = {
                        'total_shown': row.total,
                        'interactions': row.with_action,
                        'saves': row.saved_count,
                        'interaction_rate': row.with_action / row.total if row.total > 0 else 0,
                        'save_rate': row.saved_count / row.total if row.total > 0 else 0
                    }

                # 평균 추천 점수
                avg_score_query = select(func.avg(Recommendation.recommendation_score)).where(and_(*conditions))
                avg_score_result = await session.execute(avg_score_query)
                avg_score = avg_score_result.scalar() or 0.0

                return {
                    'period_days': days_back,
                    'total_recommendations': total_recommendations,
                    'average_score': float(avg_score),
                    'action_statistics': action_stats,
                    'type_performance': type_stats,
                    'overall_engagement_rate': sum(stats['count'] for stats in action_stats.values() if stats) / total_recommendations if total_recommendations > 0 else 0
                }

        except Exception as e:
            log.error(f"추천 성능 통계 조회 오류: {e}")
            return {}

    async def get_user_recommendation_preferences(
        self, user_id: int, days_back: int = 90
    ) -> Dict[str, Any]:
        """
        사용자의 추천 선호도 패턴을 분석합니다.

        Args:
            user_id: 사용자 ID
            days_back: 분석 기간 (일)

        Returns:
            사용자 선호도 분석 결과
        """
        try:
            async for session in get_async_session():
                cutoff_date = datetime.utcnow() - timedelta(days=days_back)

                # 사용자의 추천 상호작용 히스토리
                user_recommendations = await session.execute(
                    select(Recommendation).where(
                        and_(
                            Recommendation.user_id == user_id,
                            Recommendation.shown_at >= cutoff_date,
                            Recommendation.user_action.isnot(None)
                        )
                    ).order_by(desc(Recommendation.action_at))
                )

                recommendations = user_recommendations.scalars().all()

                if not recommendations:
                    return {'message': '분석할 상호작용 데이터가 없습니다.'}

                # 선호 분석
                preferred_types = {}
                keyword_preferences = {}
                action_patterns = {}

                for rec in recommendations:
                    # 추천 타입별 선호도
                    rec_type = rec.recommendation_type
                    action = rec.user_action
                    
                    if rec_type not in preferred_types:
                        preferred_types[rec_type] = {'positive': 0, 'negative': 0, 'neutral': 0}
                    
                    if action in ['saved', 'clicked', 'shared']:
                        preferred_types[rec_type]['positive'] += 1
                    elif action in ['dismissed']:
                        preferred_types[rec_type]['negative'] += 1
                    else:
                        preferred_types[rec_type]['neutral'] += 1

                    # 액션 패턴
                    if action not in action_patterns:
                        action_patterns[action] = 0
                    action_patterns[action] += 1

                    # 키워드 선호도 분석
                    reasoning = rec.reasoning or {}
                    factors = reasoning.get('factors', [])
                    for factor in factors:
                        if factor.get('factor') == 'keyword_match':
                            keywords = factor.get('keywords', [])
                            for keyword in keywords:
                                if keyword not in keyword_preferences:
                                    keyword_preferences[keyword] = {'positive': 0, 'negative': 0}
                                
                                if action in ['saved', 'clicked', 'shared']:
                                    keyword_preferences[keyword]['positive'] += 1
                                elif action in ['dismissed']:
                                    keyword_preferences[keyword]['negative'] += 1

                # 선호도 점수 계산
                type_scores = {}
                for rec_type, counts in preferred_types.items():
                    total = sum(counts.values())
                    if total > 0:
                        score = (counts['positive'] - counts['negative']) / total
                        type_scores[rec_type] = {
                            'preference_score': score,
                            'interaction_count': total,
                            'breakdown': counts
                        }

                keyword_scores = {}
                for keyword, counts in keyword_preferences.items():
                    total = counts['positive'] + counts['negative']
                    if total > 0:
                        score = (counts['positive'] - counts['negative']) / total
                        keyword_scores[keyword] = {
                            'preference_score': score,
                            'interaction_count': total
                        }

                return {
                    'user_id': user_id,
                    'analysis_period_days': days_back,
                    'total_interactions': len(recommendations),
                    'recommendation_type_preferences': type_scores,
                    'keyword_preferences': dict(sorted(keyword_scores.items(), key=lambda x: x[1]['preference_score'], reverse=True)[:20]),
                    'action_distribution': action_patterns,
                    'engagement_level': len(recommendations) / days_back  # 일평균 상호작용
                }

        except Exception as e:
            log.error(f"사용자 선호도 분석 오류: {e}")
            return {}

    async def get_recommendation_insights(
        self, days_back: int = 7
    ) -> Dict[str, Any]:
        """
        시스템 전체의 추천 인사이트를 생성합니다.

        Args:
            days_back: 분석 기간 (일)

        Returns:
            시스템 인사이트 데이터
        """
        try:
            async for session in get_async_session():
                cutoff_date = datetime.utcnow() - timedelta(days=days_back)

                # 가장 성공적인 추천들 (저장율 기준)
                successful_recs_query = select(
                    Recommendation.recommended_url,
                    func.count(Recommendation.id).label('total_shown'),
                    func.sum(
                        func.case(
                            (Recommendation.user_action == 'saved', 1),
                            else_=0
                        )
                    ).label('saves')
                ).where(
                    Recommendation.shown_at >= cutoff_date
                ).group_by(
                    Recommendation.recommended_url
                ).having(
                    func.count(Recommendation.id) >= 5  # 최소 5회 이상 추천된 것만
                ).order_by(
                    desc(text('saves::float / total_shown'))
                ).limit(10)

                successful_result = await session.execute(successful_recs_query)
                successful_recommendations = []
                for row in successful_result.fetchall():
                    successful_recommendations.append({
                        'url': row.recommended_url,
                        'total_shown': row.total_shown,
                        'saves': row.saves,
                        'save_rate': row.saves / row.total_shown if row.total_shown > 0 else 0
                    })

                # 추천 타입별 성능 트렌드
                type_trends = {}
                for rec_type in ['cluster_based', 'content_based', 'popularity_based', 'search_based']:
                    daily_stats = await session.execute(
                        select(
                            func.date(Recommendation.shown_at).label('date'),
                            func.count(Recommendation.id).label('shown'),
                            func.sum(
                                func.case(
                                    (Recommendation.user_action.in_(['saved', 'clicked']), 1),
                                    else_=0
                                )
                            ).label('positive_actions')
                        ).where(
                            and_(
                                Recommendation.recommendation_type == rec_type,
                                Recommendation.shown_at >= cutoff_date
                            )
                        ).group_by(
                            func.date(Recommendation.shown_at)
                        ).order_by(
                            func.date(Recommendation.shown_at)
                        )
                    )

                    daily_data = []
                    for row in daily_stats.fetchall():
                        daily_data.append({
                            'date': row.date.isoformat(),
                            'shown': row.shown,
                            'positive_actions': row.positive_actions,
                            'engagement_rate': row.positive_actions / row.shown if row.shown > 0 else 0
                        })
                    
                    type_trends[rec_type] = daily_data

                return {
                    'analysis_period_days': days_back,
                    'top_performing_content': successful_recommendations,
                    'recommendation_type_trends': type_trends,
                    'generated_at': datetime.utcnow().isoformat()
                }

        except Exception as e:
            log.error(f"추천 인사이트 생성 오류: {e}")
            return {}

    async def _process_feedback_for_profile_update(
        self,
        session: AsyncSession,
        recommendation: Recommendation,
        action: str
    ) -> None:
        """피드백을 기반으로 사용자 프로파일을 업데이트합니다."""
        try:
            # 피드백 가중치 적용
            feedback_weight = self.feedback_weights.get(action, 0)
            if feedback_weight == 0:
                return

            # 사용자 프로파일 조회
            user_profile = await session.get(UserProfile, recommendation.user_id)
            if not user_profile:
                return

            # 추천 이유에서 키워드 추출하여 가중치 조정
            reasoning = recommendation.reasoning or {}
            factors = reasoning.get('factors', [])
            
            for factor in factors:
                if factor.get('factor') == 'keyword_match':
                    keywords = factor.get('keywords', [])
                    if keywords and user_profile.keywords_frequency:
                        for keyword in keywords:
                            if keyword in user_profile.keywords_frequency:
                                freq_data = user_profile.keywords_frequency[keyword]
                                if isinstance(freq_data, dict):
                                    current_weight = freq_data.get('weight', 1.0)
                                    new_weight = max(0.1, min(2.0, current_weight + feedback_weight * 0.1))
                                    freq_data['weight'] = new_weight
                                    freq_data['last_feedback'] = datetime.utcnow().isoformat()

            await session.commit()

        except Exception as e:
            log.error(f"프로파일 피드백 처리 오류: {e}")

    async def cleanup_old_recommendations(self, days_to_keep: int = 90) -> int:
        """오래된 추천 기록을 정리합니다."""
        try:
            async for session in get_async_session():
                cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
                
                # 오래된 기록 삭제
                delete_query = select(Recommendation).where(
                    Recommendation.shown_at < cutoff_date
                )
                result = await session.execute(delete_query)
                old_recommendations = result.scalars().all()
                
                for rec in old_recommendations:
                    await session.delete(rec)
                
                await session.commit()
                
                deleted_count = len(old_recommendations)
                log.info(f"오래된 추천 기록 {deleted_count}개 정리 완료")
                return deleted_count

        except Exception as e:
            log.error(f"추천 기록 정리 오류: {e}")
            return 0 