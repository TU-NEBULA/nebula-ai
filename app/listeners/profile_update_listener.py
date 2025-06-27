"""
실시간 프로파일 업데이트 리스너

사용자의 북마크, 채팅, 추천 상호작용을 실시간으로 감지하여
프로파일 업데이트와 클러스터링 재계산을 트리거합니다.
"""

import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.models.user_profile import UserProfile
from app.models.bookmark import Bookmark
from app.services.user_profile_processor import UserProfileProcessor
from app.services.clustering_service import ClusteringService
from app.services.vector_service import VectorService
from app.adapters.profile_api_adapter import ProfileAPIAdapter
from app.repositories.user_profile_repository import UserProfileRepository


@dataclass
class ProfileUpdateEvent:
    """프로파일 업데이트 이벤트 데이터"""
    user_id: int
    event_type: str  # bookmark_added, bookmark_removed, chat_interaction, recommendation_feedback
    event_data: Dict[str, Any]
    timestamp: datetime
    priority: int = 1  # 1(높음) ~ 3(낮음)
    requires_clustering_update: bool = False


class RealTimeProfileUpdateListener:
    """실시간 프로파일 업데이트 리스너"""

    def __init__(self):
        self.profile_processor = UserProfileProcessor()
        self.clustering_service = ClusteringService()
        self.vector_service = VectorService()
        self.profile_repository = UserProfileRepository()
        self.api_adapter = ProfileAPIAdapter()
        
        # 이벤트 큐와 처리 설정
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.batch_size = 10
        self.batch_timeout = 30  # 초
        self.clustering_threshold = 5  # 클러스터링 업데이트 임계값
        
        # 콜백 및 상태 관리
        self.event_callbacks: Dict[str, List[Callable]] = {}
        self.is_processing = False
        self.processed_events_count = 0
        
        # 클러스터 변경 감지를 위한 캐시
        self.user_cluster_cache: Dict[int, int] = {}

    async def start_processing(self):
        """이벤트 처리 시작"""
        if self.is_processing:
            logger.warning("프로파일 업데이트 리스너가 이미 실행 중입니다.")
            return
            
        self.is_processing = True
        logger.info("🚀 실시간 프로파일 업데이트 리스너 시작")
        
        # 백그라운드 태스크 시작
        asyncio.create_task(self._batch_process_events())
        asyncio.create_task(self._periodic_clustering_check())

    async def stop_processing(self):
        """이벤트 처리 중지"""
        self.is_processing = False
        logger.info("🛑 실시간 프로파일 업데이트 리스너 중지")

    async def handle_bookmark_event(
        self,
        user_id: int,
        event_type: str,  # 'added', 'removed', 'updated'
        bookmark_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """북마크 이벤트 처리"""
        try:
            # 이벤트 생성
            event = ProfileUpdateEvent(
                user_id=user_id,
                event_type=f"bookmark_{event_type}",
                event_data={
                    "bookmark": bookmark_data,
                    "metadata": metadata or {}
                },
                timestamp=datetime.now(),
                priority=1 if event_type == "added" else 2,
                requires_clustering_update=True
            )
            
            # 이벤트 큐에 추가
            await self.event_queue.put(event)
            
            logger.debug(f"📖 북마크 이벤트 큐 추가: User {user_id}, Type: {event_type}")
            
            # 즉시 처리가 필요한 중요 이벤트인 경우
            if event_type == "added" and self._is_significant_bookmark(bookmark_data):
                await self._process_high_priority_event(event)
                
        except Exception as e:
            logger.error(f"❌ 북마크 이벤트 처리 실패: {e}")

    async def handle_chat_interaction_event(
        self,
        user_id: int,
        chat_data: Dict[str, Any],
        interaction_type: str = "message"
    ):
        """채팅 상호작용 이벤트 처리"""
        try:
            event = ProfileUpdateEvent(
                user_id=user_id,
                event_type=f"chat_{interaction_type}",
                event_data=chat_data,
                timestamp=datetime.now(),
                priority=2,
                requires_clustering_update=False
            )
            
            await self.event_queue.put(event)
            logger.debug(f"💬 채팅 이벤트 큐 추가: User {user_id}")
            
        except Exception as e:
            logger.error(f"❌ 채팅 이벤트 처리 실패: {e}")

    async def handle_recommendation_feedback_event(
        self,
        user_id: int,
        recommendation_id: str,
        action: str,  # 'clicked', 'saved', 'dismissed', 'ignored'
        feedback_data: Optional[Dict[str, Any]] = None
    ):
        """추천 피드백 이벤트 처리"""
        try:
            # 피드백 중요도 계산
            priority = 1 if action in ["clicked", "saved"] else 3
            requires_clustering = action in ["clicked", "saved"]
            
            event = ProfileUpdateEvent(
                user_id=user_id,
                event_type="recommendation_feedback",
                event_data={
                    "recommendation_id": recommendation_id,
                    "action": action,
                    "feedback_data": feedback_data or {}
                },
                timestamp=datetime.now(),
                priority=priority,
                requires_clustering_update=requires_clustering
            )
            
            await self.event_queue.put(event)
            logger.debug(f"🎯 추천 피드백 이벤트 큐 추가: User {user_id}, Action: {action}")
            
        except Exception as e:
            logger.error(f"❌ 추천 피드백 이벤트 처리 실패: {e}")

    async def _batch_process_events(self):
        """이벤트 배치 처리"""
        while self.is_processing:
            try:
                events_batch = []
                
                # 배치 수집 (최대 batch_size개 또는 timeout까지)
                try:
                    # 첫 번째 이벤트 대기
                    first_event = await asyncio.wait_for(
                        self.event_queue.get(), 
                        timeout=self.batch_timeout
                    )
                    events_batch.append(first_event)
                    
                    # 추가 이벤트 수집
                    for _ in range(self.batch_size - 1):
                        try:
                            event = await asyncio.wait_for(
                                self.event_queue.get(), 
                                timeout=1.0
                            )
                            events_batch.append(event)
                        except asyncio.TimeoutError:
                            break
                            
                except asyncio.TimeoutError:
                    # 타임아웃으로 인한 빈 배치는 건너뛰기
                    continue
                
                if events_batch:
                    await self._process_events_batch(events_batch)
                    
            except Exception as e:
                logger.error(f"❌ 이벤트 배치 처리 중 오류: {e}")
                await asyncio.sleep(5)  # 오류 발생 시 잠시 대기

    def _is_significant_bookmark(self, bookmark_data: Dict[str, Any]) -> bool:
        """북마크의 중요도 판단"""
        keywords = bookmark_data.get('keywords', [])
        content_length = len(bookmark_data.get('content', ''))
        
        return len(keywords) >= 3 or content_length >= 1000

    async def _process_high_priority_event(self, event: ProfileUpdateEvent):
        """고우선순위 이벤트 즉시 처리"""
        try:
            logger.info(f"⚡ 고우선순위 이벤트 즉시 처리: User {event.user_id}")
            
            async for session in get_async_session():
                await self._update_user_profile_from_events(
                    session, event.user_id, [event]
                )
                
        except Exception as e:
            logger.error(f"❌ 고우선순위 이벤트 처리 실패: {e}")

    async def _process_events_batch(self, events: List[ProfileUpdateEvent]):
        """이벤트 배치 처리 실행"""
        if not events:
            return
            
        logger.info(f"📦 이벤트 배치 처리 시작: {len(events)}개 이벤트")
        
        try:
            # 사용자별로 이벤트 그룹핑
            user_events = {}
            clustering_users = set()
            
            for event in events:
                if event.user_id not in user_events:
                    user_events[event.user_id] = []
                user_events[event.user_id].append(event)
                
                if event.requires_clustering_update:
                    clustering_users.add(event.user_id)
            
            # 사용자별 프로파일 업데이트
            async for session in get_async_session():
                for user_id, user_event_list in user_events.items():
                    await self._update_user_profile_from_events(
                        session, user_id, user_event_list
                    )
                    
                    # 클러스터 변경 감지
                    if user_id in clustering_users:
                        await self._check_cluster_change(session, user_id)
            
            # 배치 단위 클러스터링 업데이트 (필요시)
            if len(clustering_users) >= self.clustering_threshold:
                await self._trigger_clustering_update(list(clustering_users))
            
            self.processed_events_count += len(events)
            logger.info(f"✅ 이벤트 배치 처리 완료: {len(events)}개 이벤트")
            
        except Exception as e:
            logger.error(f"❌ 이벤트 배치 처리 실패: {e}")

    async def _update_user_profile_from_events(
        self,
        session: AsyncSession,
        user_id: int,
        events: List[ProfileUpdateEvent]
    ):
        """이벤트 기반 사용자 프로파일 업데이트"""
        try:
            # 현재 프로파일 조회
            user_profile = await self.profile_repository.get_user_profile(session, user_id)
            
            if not user_profile:
                logger.warning(f"사용자 {user_id} 프로파일이 없습니다.")
                return
            
            # 프로파일 업데이트 적용
            user_profile.last_updated = datetime.now()
            user_profile.update_count = (user_profile.update_count or 0) + 1
            
            # 데이터베이스 저장
            await self.profile_repository.update_user_profile(session, user_profile)
                
            logger.debug(f"사용자 {user_id} 프로파일 업데이트 완료")
            
        except Exception as e:
            logger.error(f"❌ 사용자 {user_id} 프로파일 업데이트 실패: {e}")

    async def _check_cluster_change(self, session: AsyncSession, user_id: int):
        """사용자 클러스터 변경 감지"""
        try:
            # 현재 클러스터 조회
            user_profile = await self.profile_repository.get_user_profile(session, user_id)
            if not user_profile:
                return
                
            current_cluster = user_profile.similarity_cluster
            previous_cluster = self.user_cluster_cache.get(user_id)
            
            # 클러스터 변경 감지
            if previous_cluster and current_cluster != previous_cluster:
                logger.info(f"🔄 사용자 {user_id} 클러스터 변경: {previous_cluster} → {current_cluster}")
            
            # 캐시 업데이트
            self.user_cluster_cache[user_id] = current_cluster
            
        except Exception as e:
            logger.error(f"❌ 클러스터 변경 감지 실패: {e}")

    async def _periodic_clustering_check(self):
        """주기적 클러스터링 상태 확인"""
        while self.is_processing:
            try:
                await asyncio.sleep(300)  # 5분마다 체크
                logger.debug("주기적 클러스터링 상태 체크")
                
            except Exception as e:
                logger.error(f"❌ 주기적 클러스터링 체크 실패: {e}")

    async def _trigger_clustering_update(self, user_ids: List[int]):
        """클러스터링 업데이트 트리거"""
        try:
            logger.info(f"🔄 클러스터링 업데이트 트리거: {len(user_ids)}명 사용자")
            
        except Exception as e:
            logger.error(f"❌ 클러스터링 업데이트 트리거 실패: {e}")

    def register_event_callback(self, event_type: str, callback: Callable):
        """이벤트 콜백 등록"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        self.event_callbacks[event_type].append(callback)

    def get_processing_stats(self) -> Dict[str, Any]:
        """처리 통계 조회"""
        return {
            "is_processing": self.is_processing,
            "queue_size": self.event_queue.qsize(),
            "processed_events": self.processed_events_count,
            "cached_users": len(self.user_cluster_cache)
        } 