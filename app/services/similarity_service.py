"""
북마크 유사도 계산 서비스

새로운 북마크와 기존 북마크들 간의 유사도를 계산하여
관련성이 높은 북마크들을 찾는 서비스입니다.
"""
import logging
from typing import List, Dict, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor

import openai
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings
from app.services.vector_service import VectorService

log = logging.getLogger(__name__)

class SimilarityService:
    """북마크 유사도 계산 서비스"""
    
    def __init__(self):
        self.vector_service = VectorService()
        self.similarity_threshold = settings.SIMILARITY_THRESHOLD  # 환경변수에서 가져오기
        self.max_similar_bookmarks = settings.MAX_SIMILAR_BOOKMARKS  # 환경변수에서 가져오기
        
    async def find_similar_bookmarks(
        self, 
        new_bookmark_content: str,
        user_id: int,
        keywords: List[str],
        summary: str
    ) -> List[Dict]:
        """
        새로운 북마크와 유사한 기존 북마크들을 찾습니다.
        
        Args:
            new_bookmark_content: 새 북마크의 텍스트 내용
            user_id: 사용자 ID
            keywords: 새 북마크의 키워드들
            summary: 새 북마크의 요약
            
        Returns:
            List[Dict]: 유사한 북마크들과 유사도 정보
            [
                {
                    "bookmark_id": str,
                    "similarity_score": float,
                    "title": str,
                    "url": str
                }
            ]
        """
        try:
            # 1. 새 북마크의 임베딩 벡터 생성
            new_embedding = await self._create_bookmark_embedding(
                new_bookmark_content, keywords, summary
            )
            
            # 2. 사용자의 기존 북마크들 조회
            existing_bookmarks = await self._get_user_bookmarks(user_id)
            
            if not existing_bookmarks:
                log.info("사용자 %s의 기존 북마크가 없습니다.", user_id)
                return []
            
            # 3. 유사도 계산
            similar_bookmarks = await self._calculate_similarities(
                new_embedding, existing_bookmarks
            )
            
            # 4. 임계값 필터링 및 정렬
            filtered_similar = [
                bookmark for bookmark in similar_bookmarks 
                if bookmark["similarity_score"] >= self.similarity_threshold
            ]
            
            # 5. 유사도 순으로 정렬하여 상위 N개 반환
            filtered_similar.sort(
                key=lambda x: x["similarity_score"], 
                reverse=True
            )
            
            result = filtered_similar[:self.max_similar_bookmarks]
            
            log.info(
                "사용자 %s의 새 북마크와 유사한 북마크 %d개 발견", 
                user_id, len(result)
            )
            
            return result
            
        except Exception as e:
            log.error("유사도 계산 중 오류 발생: %s", e)
            return []
    
    async def _create_bookmark_embedding(
        self, 
        content: str, 
        keywords: List[str], 
        summary: str
    ) -> np.ndarray:
        """북마크 임베딩 벡터 생성"""
        
        # 텍스트 조합: 내용 + 키워드 + 요약
        combined_text = f"{content}\n키워드: {', '.join(keywords)}\n요약: {summary}"
        
        # OpenAI 임베딩 생성
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(
                executor,
                lambda: openai.embeddings.create(
                    model=settings.OPENAI_EMBED_MODEL,
                    input=combined_text
                )
            )
        
        embedding = np.array(response.data[0].embedding)
        return embedding
    
    async def _get_user_bookmarks(self, user_id: int) -> List[Dict]:
        """사용자의 기존 북마크들 조회"""
        try:
            # TODO: 실제로는 데이터베이스 세션이 필요하지만 임시로 빈 리스트 반환
            # VectorService를 통해 사용자 북마크 조회하려면 AsyncSession이 필요함
            log.info("사용자 %s의 북마크 조회 중... (현재는 Mock 데이터)", user_id)
            
            # 임시로 빈 리스트 반환 (실제 구현에서는 데이터베이스 연결 필요)
            return []
            
        except Exception as e:
            log.error("사용자 북마크 조회 중 오류: %s", e)
            return []
    
    async def _calculate_similarities(
        self, 
        new_embedding: np.ndarray, 
        existing_bookmarks: List[Dict]
    ) -> List[Dict]:
        """기존 북마크들과의 유사도 계산"""
        
        similar_bookmarks = []
        
        for bookmark in existing_bookmarks:
            try:
                # 기존 북마크의 임베딩 벡터
                existing_embedding = np.array(bookmark["embedding"])
                
                # 코사인 유사도 계산
                similarity = cosine_similarity(
                    new_embedding.reshape(1, -1),
                    existing_embedding.reshape(1, -1)
                )[0][0]
                
                similar_bookmarks.append({
                    "bookmark_id": bookmark["id"],
                    "similarity_score": float(similarity),
                    "title": bookmark["title"],
                    "url": bookmark["url"]
                })
                
            except Exception as e:
                log.warning("북마크 %s 유사도 계산 실패: %s", bookmark["id"], e)
                continue
        
        return similar_bookmarks 