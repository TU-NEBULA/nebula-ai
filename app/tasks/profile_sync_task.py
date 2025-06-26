"""
User AI Profile → User Profile 실시간 동기화 태스크

🔄 실시간 동기화 (3시간마다)
- AI 프로필 변경사항을 빠르게 User Profile에 반영
- 활성 사용자 우선 처리로 실시간성 강화
- 경량화된 데이터 동기화에 집중

📊 vs 새벽 배치 (daily_profile_monitor.py)
- 실시간: 빠른 데이터 동기화
- 배치: 품질 분석 + 문제 프로필 수정
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

from app.core.database import get_async_session
from app.repositories.ai_profile_repository import AIProfileRepository
from app.repositories.user_profile_repository import UserProfileRepository
from app.services.user_profile_processor import UserProfileProcessor

logger = logging.getLogger(__name__)


class ProfileSyncTask:
    """AI Profile → User Profile 동기화 태스크"""
    
    def __init__(self):
        self.batch_size = 50  # 한 번에 처리할 사용자 수
        self.sync_interval_hours = 3  # 3시간마다 동기화
        self.priority_sync_for_active_users = True  # 활성 사용자 우선 처리
        
    async def run_sync_batch(self) -> Dict[str, Any]:
        """배치 동기화 실행"""
        start_time = datetime.now(timezone.utc)
        
        try:
            logger.info("🔄 User Profile 배치 동기화 시작")
            
            # 업데이트 대상 사용자 조회
            users_to_sync = await self._get_users_needing_sync()
            
            if not users_to_sync:
                logger.info("📋 동기화 대상 사용자 없음")
                return {
                    "success": True,
                    "users_processed": 0,
                    "processing_time": 0.0,
                    "message": "동기화 대상 없음"
                }
            
            # 배치 단위로 처리
            total_processed = 0
            total_failed = 0
            
            for i in range(0, len(users_to_sync), self.batch_size):
                batch = users_to_sync[i:i + self.batch_size]
                
                logger.info(f"📦 배치 {i//self.batch_size + 1} 처리 중... ({len(batch)}명)")
                
                batch_results = await self._process_user_batch(batch)
                total_processed += batch_results['processed']
                total_failed += batch_results['failed']
                
                # 배치 간 짧은 대기 (DB 부하 분산)
                await asyncio.sleep(1)
            
            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()
            
            logger.info(
                f"✅ 배치 동기화 완료 - 처리: {total_processed}명, 실패: {total_failed}명, "
                f"소요시간: {processing_time:.2f}초"
            )
            
            return {
                "success": True,
                "users_processed": total_processed,
                "users_failed": total_failed,
                "processing_time": processing_time,
                "sync_timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 배치 동기화 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "users_processed": 0,
                "processing_time": 0.0
            }
    
    async def _get_users_needing_sync(self) -> List[int]:
        """동기화가 필요한 사용자 목록 조회"""
        try:
            async for session in get_async_session():
                # AI Profile이 업데이트되었지만 User Profile은 오래된 사용자들
                from sqlalchemy import text
                
                query = text("""
                    SELECT DISTINCT uap.user_id::integer,
                           uap.updated_at,
                           CASE 
                               WHEN uap.updated_at > NOW() - INTERVAL '24 hours' THEN 1
                               WHEN uap.updated_at > NOW() - INTERVAL '7 days' THEN 2  
                               ELSE 3
                           END as priority_level
                    FROM user_ai_profiles uap
                    LEFT JOIN user_profiles up ON uap.user_id::integer = up.user_id
                    WHERE (
                        -- AI Profile이 User Profile보다 최근에 업데이트된 경우
                        up.id IS NULL OR 
                        uap.updated_at > up.updated_at OR
                        -- 또는 3시간 이상 동기화되지 않은 경우
                        up.updated_at < NOW() - INTERVAL '3 hours'
                    )
                    AND uap.current_interests IS NOT NULL  -- 실제 관심사가 있는 사용자만
                    AND LENGTH(TRIM(uap.current_interests)) > 0
                    ORDER BY 
                        priority_level ASC,  -- 최근 업데이트 우선
                        uap.updated_at DESC
                    LIMIT 200  -- 최대 200명까지
                """)
                
                result = await session.execute(query)
                user_ids = [row[0] for row in result.fetchall()]
                
                logger.info(f"🎯 동기화 대상 사용자: {len(user_ids)}명")
                return user_ids
                
        except Exception as e:
            logger.error(f"❌ 동기화 대상 조회 실패: {e}")
            return []
    
    async def _process_user_batch(self, user_ids: List[int]) -> Dict[str, int]:
        """사용자 배치 처리"""
        processed = 0
        failed = 0
        
        async for session in get_async_session():
            try:
                # Repository 및 프로세서 초기화
                ai_profile_repo = AIProfileRepository()
                user_profile_repo = UserProfileRepository()
                
                processor = UserProfileProcessor({
                    'ai_profile_repo': ai_profile_repo,
                    'user_profile_repo': user_profile_repo
                })
                
                for user_id in user_ids:
                    try:
                        # AI Profile 데이터 조회
                        ai_profiles = await ai_profile_repo.get_user_ai_profiles(session, user_id)
                        
                        if not ai_profiles:
                            continue
                        
                        # AI Profile → User Profile 동기화
                        sync_result = await self._sync_single_user(
                            session, user_id, ai_profiles[0], processor
                        )
                        
                        if sync_result:
                            processed += 1
                            logger.debug(f"✅ 사용자 {user_id} 동기화 완료")
                        else:
                            failed += 1
                            logger.warning(f"⚠️ 사용자 {user_id} 동기화 실패")
                    
                    except Exception as user_error:
                        failed += 1
                        logger.error(f"❌ 사용자 {user_id} 처리 실패: {user_error}")
                
            except Exception as batch_error:
                logger.error(f"❌ 배치 처리 실패: {batch_error}")
                failed += len(user_ids)
        
        return {"processed": processed, "failed": failed}
    
    async def _sync_single_user(
        self, 
        session, 
        user_id: int, 
        ai_profile, 
        processor: UserProfileProcessor
    ) -> bool:
        """단일 사용자 동기화"""
        try:
            # AI Profile에서 관심사 및 빈도 정보 추출
            interests = []
            keywords_frequency = {}
            
            if ai_profile.current_interests:
                # 쉼표로 구분된 키워드들을 리스트로 변환
                keywords_list = [kw.strip() for kw in ai_profile.current_interests.split(",") if kw.strip()]
                interests = keywords_list[:50]
                
                # 키워드 빈도 정보 생성 (순서 기반 가중치)
                for i, keyword in enumerate(interests):
                    # 앞쪽 키워드일수록 높은 가중치 (2.0 → 1.0)
                    weight = max(2.0 - (i * 0.02), 1.0)  # 50개 기준으로 감소율 조정
                    frequency = max(20 - i // 2, 1)  # 빈도도 순서에 따라 감소 (더 넓은 범위)
                    
                    keywords_frequency[keyword] = {
                        "frequency": frequency,
                        "weight": round(weight, 2),
                        "last_seen": datetime.now().isoformat(),
                        "rank": i + 1  # 순위 정보 추가
                    }
            
            # 활동 패턴 분석
            activity_patterns = {
                "total_sessions": getattr(ai_profile, 'total_chat_sessions', 0),
                "total_messages": getattr(ai_profile, 'total_messages', 0),
                "avg_session_duration": getattr(ai_profile, 'avg_session_duration_minutes', 0) or 0,
                "preferred_response_style": getattr(ai_profile, 'ai_interaction_style', 'detailed'),
                "preferred_language": getattr(ai_profile, 'learning_preferences', 'ko'),
                "last_sync": datetime.now(timezone.utc).isoformat()
            }
            
            # User Profile 업데이트 또는 생성 (키워드 빈도 포함)
            await processor.sync_from_ai_profile(
                user_id=user_id,
                interests=interests,
                keywords_frequency=keywords_frequency,  # 🆕 키워드 빈도 정보 추가
                activity_patterns=activity_patterns,
                ai_profile_data=ai_profile
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 사용자 {user_id} 동기화 실패: {e}")
            return False


async def run_profile_sync():
    """스케줄러에서 호출할 메인 함수"""
    task = ProfileSyncTask()
    result = await task.run_sync_batch()
    
    logger.info(f"📊 프로필 동기화 결과: {result}")
    return result


# Celery 태스크로 실시간 동기화 설정
from app.core.celery_worker import celery
from celery.schedules import crontab

@celery.task(
    name="tasks.profile_sync_realtime",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 300},
    retry_backoff=True,
    retry_jitter=True,
    queue="monitoring",
)
def profile_sync_realtime_task(self) -> dict:
    """Celery 태스크: 실시간 프로필 동기화 (3시간마다)"""
    logger.info("🔄 실시간 프로필 동기화 시작")
    
    try:
        import asyncio
        result = asyncio.run(run_profile_sync())
        logger.info("✅ 실시간 프로필 동기화 완료")
        return result
    except Exception as e:
        logger.error(f"❌ 실시간 프로필 동기화 실패: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

def setup_realtime_sync_schedule():
    """실시간 동기화 스케줄 설정"""
    from app.core.celery_worker import celery
    
    # 기존 beat_schedule에 추가
    if not hasattr(celery.conf, 'beat_schedule'):
        celery.conf.beat_schedule = {}
    
    # 프로덕션 스케줄 - 3시간마다 실행
    celery.conf.beat_schedule.update({
        'realtime-profile-sync': {
            'task': 'tasks.profile_sync_realtime',
            'schedule': crontab(minute=0, hour='*/3'),  # 3시간마다 실행 (0시, 3시, 6시, 9시, 12시, 15시, 18시, 21시)
            'options': {
                'queue': 'monitoring',  # monitoring 큐에 라우팅
                'expires': 1800,  # 30분 후 만료
                'retry': True,
                'retry_policy': {
                    'max_retries': 2,
                    'interval_start': 300,  # 5분
                    'interval_step': 300,
                    'interval_max': 900,  # 15분
                }
            }
        }
    })
    
    logger.info("📅 프로필 동기화 스케줄 설정 완료 (3시간마다)")


if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(run_profile_sync()) 