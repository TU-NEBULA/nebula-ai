"""
User AI Profile → User Profile 배치 동기화 태스크

실시간으로 쌓인 AI 프로필 데이터를 주기적으로 User Profile에 반영하여
벡터 임베딩과 개인화 추천 시스템을 업데이트합니다.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

from app.database.connection import get_async_session
from app.repositories.bookmark_repository import AIProfileRepository
from app.repositories.user_profile_repository import UserProfileRepository
from app.services.user_profile_processor import UserProfileProcessor

logger = logging.getLogger(__name__)


class ProfileSyncTask:
    """AI Profile → User Profile 동기화 태스크"""
    
    def __init__(self):
        self.batch_size = 50  # 한 번에 처리할 사용자 수
        self.sync_interval_hours = 6  # 6시간마다 동기화
        
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
                    SELECT DISTINCT uap.user_id::integer
                    FROM user_ai_profiles uap
                    LEFT JOIN user_profiles up ON uap.user_id::integer = up.user_id
                    WHERE (
                        -- AI Profile이 User Profile보다 최근에 업데이트된 경우
                        up.id IS NULL OR 
                        uap.updated_at > up.last_updated_at OR
                        -- 또는 6시간 이상 동기화되지 않은 경우
                        up.last_updated_at < NOW() - INTERVAL '6 hours'
                    )
                    AND uap.total_chat_sessions > 0  -- 실제 활동이 있는 사용자만
                    ORDER BY uap.updated_at DESC
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
            # AI Profile에서 관심사 추출
            interests = []
            if ai_profile.frequent_keywords:
                interests.extend(ai_profile.frequent_keywords[:30])  # 상위 30개
            
            # 활동 패턴 분석
            activity_patterns = {
                "total_sessions": ai_profile.total_chat_sessions,
                "total_messages": ai_profile.total_messages,
                "avg_session_duration": ai_profile.avg_session_duration_minutes or 0,
                "preferred_response_style": ai_profile.preferred_response_style,
                "preferred_language": ai_profile.preferred_language,
                "last_sync": datetime.now(timezone.utc).isoformat()
            }
            
            # User Profile 업데이트 또는 생성
            await processor.sync_from_ai_profile(
                user_id=user_id,
                interests=interests,
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


# 스케줄러 설정 (예시 - APScheduler 사용)
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# 
# scheduler = AsyncIOScheduler()
# scheduler.add_job(
#     run_profile_sync,
#     'interval',
#     hours=6,  # 6시간마다 실행
#     id='profile_sync_task',
#     replace_existing=True
# )


if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(run_profile_sync()) 