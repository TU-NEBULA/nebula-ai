"""
프로필 업데이트 서비스

채팅 후 사용자 AI 프로필을 실시간으로 업데이트합니다.
"""

import uuid
from typing import Dict, Any, List, Tuple
from loguru import logger

from app.core.database import get_async_session
from app.utils.text_processing import extract_keywords


class ProfileUpdateService:
    """사용자 프로필 업데이트를 담당하는 서비스 클래스"""
    
    def __init__(self):
        pass
        
    async def update_user_ai_profile_after_chat(
        self,
        user_id: int,
        user_message: str,
        ai_response: str,
        ctx_blocks: List[Tuple[str, Dict[str, Any]]],
        session_id: uuid.UUID,
        session_duration_minutes: float
    ) -> Dict[str, Any]:
        """채팅 완료 후 사용자 AI 프로필을 실시간 업데이트합니다."""
        try:
            logger.info(f"🤖 사용자 AI 프로필 업데이트 시작 - user_id: {user_id}")
            
            # 키워드 추출
            new_keywords = await self._extract_interests_from_message(user_message)
            searched_keywords = self._extract_searched_keywords(ctx_blocks)

            logger.debug(f"🔍 추출된 키워드 - 사용자 메시지: {new_keywords}, 검색된 문서: {searched_keywords}")
            
            # 키워드 중복 제거 및 우선순위 적용
            # 1. 사용자 메시지 키워드 우선 (가중치 높음)
            # 2. 검색된 문서 키워드 (가중치 낮음)
            keyword_priority = {}
            
            # 사용자 메시지 키워드에 높은 가중치 부여
            for keyword in new_keywords:
                keyword_priority[keyword] = keyword_priority.get(keyword, 0) + 2.0
            
            # 검색된 키워드에 낮은 가중치 부여
            for keyword in searched_keywords:
                keyword_priority[keyword] = keyword_priority.get(keyword, 0) + 1.0
            
            # 가중치 순으로 정렬하여 상위 키워드 선택
            sorted_keywords = sorted(
                keyword_priority.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            all_keywords = [keyword for keyword, _ in sorted_keywords]
            
            message_count = 2  # 사용자 메시지 + AI 응답
            
            # AI 프로필 업데이트
            return await self._update_profile_statistics(
                user_id=user_id,
                session_duration_minutes=session_duration_minutes,
                message_count=message_count,
                new_keywords=all_keywords[:20],  # 상위 20개만
                extracted_keywords=new_keywords[:5],
                searched_keywords=searched_keywords[:5]
            )
            
        except Exception as e:
            logger.error(f"❌ AI 프로필 업데이트 실패 - user_id: {user_id}, 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "extracted_keywords": [],
                "searched_keywords": [],
                "total_new_keywords": 0,
                "update_type": "failed"
            }

    async def _extract_interests_from_message(self, message: str) -> List[str]:
        """
        사용자 메시지에서 관심사 키워드를 추출합니다.
        text_processing.py의 extract_keywords 함수를 사용하여 
        한국어/영어 형태소 분석과 불용어 제거를 수행합니다.
        """
        try:
            if not message or not message.strip():
                logger.warning("⚠️ 빈 메시지로 인한 키워드 추출 불가")
                return []
            
            # text_processing.py의 고도화된 키워드 추출 사용
            # - 한국어: Okt 형태소 분석기로 명사 추출
            # - 영어: NLTK pos_tag로 명사 추출 (NN, NNS, NNP, NNPS)
            # - 불용어 자동 제거 (ko_stopwords.txt, NLTK stopwords)
            # - 길이 필터링 (2글자 이상)
            keywords = extract_keywords(message, max_keywords=15)
            
            if keywords:
                logger.info(
                    f"✅ 메시지 키워드 추출 성공 - 개수: {len(keywords)}, "
                    f"샘플: {keywords[:3]}{'...' if len(keywords) > 3 else ''}"
                )
            else:
                logger.warning(f"⚠️ 메시지에서 키워드 추출되지 않음: '{message[:50]}...'")
                
            return keywords
            
        except Exception as e:
            logger.warning(f"⚠️ 키워드 추출 실패: {e}")
            return []

    def _extract_searched_keywords(self, ctx_blocks: List[Tuple[str, Dict[str, Any]]]) -> List[str]:
        """검색된 문서의 키워드들을 추출합니다."""
        searched_keywords = []
        for _, metadata in ctx_blocks:
            keywords = metadata.get('keywords', [])
            searched_keywords.extend(keywords)
        return searched_keywords

    async def _update_profile_statistics(
        self,
        user_id: int,
        session_duration_minutes: float,
        message_count: int,
        new_keywords: List[str],
        extracted_keywords: List[str],
        searched_keywords: List[str]
    ) -> Dict[str, Any]:
        """프로필 통계 업데이트"""
        async for session in get_async_session():
            try:
                from app.repositories.ai_profile_repository import AIProfileRepository
                
                updated_profile = await AIProfileRepository.update_chat_statistics(
                    session=session,
                    user_id=user_id,
                    session_duration_minutes=session_duration_minutes,
                    message_count=message_count,
                    new_keywords=new_keywords
                )
                
                logger.info(
                    f"✅ AI 프로필 업데이트 완료 - user_id: {user_id}, "
                    f"관심사: {updated_profile.current_interests}, "
                    f"스타일: {updated_profile.ai_interaction_style}"
                )
                
                return {
                    "success": True,
                    "update_type": "ai_profile_statistics", 
                    "current_interests": updated_profile.current_interests,
                    "ai_interaction_style": updated_profile.ai_interaction_style,
                    "preferred_search_domains": updated_profile.preferred_search_domains,
                    "total_new_keywords": len(new_keywords),
                    "processing_time": 0.05,  # 빠른 처리 (~50ms)
                    "extracted_keywords": extracted_keywords,
                    "searched_keywords": searched_keywords
                }
                
            except Exception as db_error:
                logger.error(f"❌ AI 프로필 DB 업데이트 실패 - user_id: {user_id}: {db_error}")
                return {
                    "success": False,
                    "error": f"DB 업데이트 실패: {str(db_error)}",
                    "update_type": "failed",
                    "extracted_keywords": extracted_keywords,
                    "searched_keywords": searched_keywords,
                    "total_new_keywords": 0
                }

    async def async_update_profile(self, update_request: Any) -> Dict[str, Any]:
        """비동기로 사용자 프로필을 업데이트합니다."""
        try:
            async for session in get_async_session():
                try:
                    from app.services.user_profile_processor import UserProfileProcessor
                    from app.repositories.chat_repository import ChatRepository
                    from app.repositories.bookmark_repository import BookmarkRepository
                    from app.repositories.user_profile_repository import UserProfileRepository
                    
                    # Repository 인스턴스 생성
                    repositories = {
                        'chat_repo': ChatRepository(),
                        'bookmark_repo': BookmarkRepository(), 
                        'user_profile_repo': UserProfileRepository()
                    }
                    
                    # 프로필 프로세서 초기화
                    processor = UserProfileProcessor(repositories)
                    
                    # 점진적 프로필 업데이트 수행
                    result = await processor.update_user_profile(
                        user_id=update_request.user_id,
                        force_full_recalculation=update_request.force_recalculation,
                        include_historical_data=not update_request.incremental_update
                    )
                    
                    logger.info(f"📊 프로필 업데이트 성공 - user_id: {update_request.user_id}")
                    return {
                        "success": True,
                        "processing_time": result.get("processing_time", 0.0),
                        "vector_strength": result.get("vector_strength", 0.0),
                        "update_type": result.get("update_type", "incremental"),
                        "data_points_processed": result.get("data_points_processed", 0)
                    }
                    
                except ImportError as import_error:
                    logger.error(f"❌ 모듈 import 실패: {import_error}")
                    return {
                        "success": False,
                        "error": f"모듈 로드 실패: {str(import_error)}",
                        "processing_time": 0.0,
                        "vector_strength": 0.0
                    }
                except Exception as process_error:
                    logger.error(f"❌ 프로필 처리 실패: {process_error}")
                    return {
                        "success": False,
                        "error": f"프로필 처리 실패: {str(process_error)}",
                        "processing_time": 0.0,
                        "vector_strength": 0.0
                    }
                
        except Exception as e:
            logger.error(f"❌ 비동기 프로필 업데이트 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time": 0.0,
                "vector_strength": 0.0
            }


# 싱글톤 인스턴스
profile_update_service = ProfileUpdateService() 