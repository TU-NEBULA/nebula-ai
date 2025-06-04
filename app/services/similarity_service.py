"""
북마크 유사도 계산 서비스

새로운 북마크와 기존 북마크들 간의 유사도를 계산하여
관련성이 높은 북마크들을 찾는 서비스입니다.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict

import numpy as np
import openai
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import get_async_session
from app.repositories.vector_repository import VectorRepository
from app.services.vector_service import VectorService

log = logging.getLogger(__name__)

class SimilarityService:
    """북마크 유사도 계산 서비스"""

    def __init__(self):
        self.vector_service = VectorService()
        self.similarity_threshold = settings.SIMILARITY_THRESHOLD
        self.max_similar_bookmarks = settings.MAX_SIMILAR_BOOKMARKS

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

            # 임베딩이 0 벡터인 경우 (오류 발생 시) 빈 리스트 반환
            if np.allclose(new_embedding, 0.0):
                log.warning("임베딩 생성 실패로 인해 유사도 계산을 건너뜁니다.")
                return []

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

        except (ConnectionError, TimeoutError, ValueError,
                ImportError, LookupError, OSError) as e:
            log.error("유사도 계산 중 오류 발생: %s", e)
            return []

    async def _create_bookmark_embedding(
        self,
        content: str,
        keywords: List[str],
        summary: str
    ) -> np.ndarray:
        """북마크 임베딩 벡터 생성"""

        try:
            # 텍스트 조합: 내용 + 키워드 + 요약
            combined_text = f"{content}\n키워드: {', '.join(keywords)}\n요약: {summary}"

            # OpenAI 임베딩 생성
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                try:
                    response = await loop.run_in_executor(
                        executor,
                        lambda: openai.embeddings.create(
                            model=settings.OPENAI_EMBED_MODEL,
                            input=combined_text
                        )
                    )
                except (openai.OpenAIError, ConnectionError, TimeoutError) as executor_e:
                    # ThreadPoolExecutor 내부 예외를 다시 raise
                    raise executor_e

            embedding = np.array(response.data[0].embedding)
            return embedding

        except (openai.OpenAIError, ValueError, TypeError,
                ConnectionError, TimeoutError) as e:
            log.error("임베딩 생성 중 오류 발생: %s", e)
            # 빈 배열을 반환하여 상위에서 처리하도록 함
            return np.array([0.0] * 1536)  # 기본 차원 크기

    async def _get_user_bookmarks(self, user_id: int) -> List[Dict]:
        """사용자의 기존 북마크들 조회"""
        try:
            async for session in get_async_session():
                try:
                    log.info("사용자 %s의 북마크 조회 중...", user_id)

                    documents = await VectorRepository.get_documents_by_user(
                        session=session,
                        user_id=user_id,
                        source_type="bookmark",
                        limit=1000
                    )

                    bookmarks = []
                    processed_source_ids = set()

                    for doc_vector in documents:
                        try:
                            # 같은 source_id의 문서는 하나만 처리 (첫 번째 청크만 사용)
                            if doc_vector.source_id in processed_source_ids:
                                continue
                            processed_source_ids.add(doc_vector.source_id)

                            bookmark_data = {
                                "id": doc_vector.source_id,  # source_id를 bookmark ID로 사용
                                "title": doc_vector.title or "제목 없음",
                                "url": doc_vector.url or "",
                                "embedding": doc_vector.embedding,
                                "content": doc_vector.content,
                                "keywords": doc_vector.keywords or [],
                                "summary": doc_vector.summary or "",
                                "created_at": doc_vector.created_at
                            }
                            bookmarks.append(bookmark_data)

                        except (SQLAlchemyError, ValueError, AttributeError, KeyError) as e:
                            log.warning("북마크 %s 처리 중 오류: %s", doc_vector.id, e)
                            continue

                    log.info("사용자 %s의 북마크 %d개 조회 완료", user_id, len(bookmarks))
                    return bookmarks

                except (SQLAlchemyError, ValueError, AttributeError, KeyError) as e:
                    log.error("북마크 조회 중 내부 오류: %s", e)
                    return []

        except (ConnectionError, TimeoutError) as e:
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

            except (ValueError, KeyError) as e:
                log.warning("북마크 %s 유사도 계산 실패: %s", bookmark["id"], e)
                continue

        return similar_bookmarks

    async def get_user_document_stats(self, user_id: int) -> Dict:
        """
        사용자의 문서 통계를 조회합니다.

        Args:
            user_id: 사용자 ID

        Returns:
            Dict: 사용자 문서 통계
        """
        try:
            async for session in get_async_session():
                try:
                    # 사용자 문서 수 조회
                    bookmark_count = await VectorRepository.get_user_document_count(
                        session=session,
                        user_id=user_id,  # int 타입 그대로 사용
                        source_type="bookmark"
                    )

                    return {
                        "user_id": user_id,
                        "total_bookmarks": bookmark_count,
                        "last_updated": None  # 필요시 구현
                    }

                except (SQLAlchemyError, ValueError, AttributeError, KeyError) as e:
                    log.error("문서 통계 조회 중 내부 오류: %s", e)
                    return {"user_id": user_id, "total_bookmarks": 0, "last_updated": None}

        except (ConnectionError, TimeoutError) as e:
            log.error("사용자 문서 통계 조회 중 오류: %s", e)
            return {"user_id": user_id, "total_bookmarks": 0, "last_updated": None}
