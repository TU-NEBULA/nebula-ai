"""
RAG (Retrieval-Augmented Generation) 검색 서비스

사용자 쿼리에 대해 PostgreSQL 벡터 데이터베이스에서 관련 문서를 검색합니다.
"""

from typing import Dict, Any, List, Tuple
from loguru import logger

from app.core.database import get_async_session
from app.services.vector_service import vector_service
from app.repositories.vector_repository import VectorRepository


class RAGSearchService:
    """RAG 검색을 담당하는 서비스 클래스"""
    
    def __init__(self, top_k: int = 10):
        self.top_k = top_k
        self.low_threshold = 0.3
        self.ultra_low_threshold = 0.15
        
    async def retrieve_context(
        self, 
        user_id: int, 
        query: str
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """PostgreSQL 벡터 데이터베이스에서 컨텍스트 검색"""
        logger.info(f"🔍 컨텍스트 검색 시작 - user_id: {user_id}, query: {query[:50]}...")

        try:
            async for db_session in get_async_session():
                # 사용자 문서 수 확인
                total_docs = await self._check_user_documents(db_session, user_id)
                if total_docs == 0:
                    logger.warning(f"⚠️ 사용자 {user_id}의 벡터 문서가 없습니다!")
                    return []
                
                # 벡터 검색 실행
                search_results = await self._perform_vector_search(
                    db_session, query, user_id
                )
                
                # 하이브리드 검색으로 보완
                if len(search_results) < 3:
                    search_results = await self._supplement_with_hybrid_search(
                        db_session, query, user_id, search_results
                    )
                
                # 결과 변환 및 필터링
                return self._convert_search_results(search_results, user_id)
                
        except Exception as e:
            logger.error(f"❌ 컨텍스트 검색 중 오류: {e}")
            return []

    async def _check_user_documents(self, db_session, user_id: int) -> int:
        """사용자의 벡터 문서 수 확인"""
        total_docs = await VectorRepository.get_user_document_count(
            session=db_session,
            user_id=user_id
        )
        logger.info(f"📊 사용자 {user_id}의 총 벡터 문서 수: {total_docs}")
        
        # 디버깅용 상태 확인
        await self._log_database_status(db_session, user_id, total_docs)
        return total_docs
    
    async def _log_database_status(self, db_session, user_id: int, total_docs: int):
        """데이터베이스 상태 로깅 (디버깅용)"""
        try:
            all_users_docs = await VectorRepository.get_user_document_count(
                session=db_session,
                user_id=None
            )
            logger.info(f"📊 전체 데이터베이스 벡터 문서 수: {all_users_docs}")
            
            if total_docs > 0:
                sample_docs = await VectorRepository.get_documents_by_user(
                    session=db_session,
                    user_id=user_id,
                    limit=3
                )
                logger.info(f"📄 샘플 문서들:")
                for i, doc in enumerate(sample_docs):
                    logger.info(f"  {i+1}. {doc.title[:50]} (타입: {doc.source_type})")
                    logger.info(f"     키워드: {doc.keywords}")
                    
        except Exception as e:
            logger.warning(f"⚠️ 데이터베이스 상태 확인 실패: {e}")

    async def _perform_vector_search(self, db_session, query: str, user_id: int):
        """벡터 검색 수행"""
        logger.info(f"🔍 벡터 검색 실행 - threshold: {self.low_threshold}, limit: {self.top_k}")
        
        try:
            search_results = await vector_service.similarity_search(
                session=db_session,
                query=query,
                user_id=user_id,
                limit=self.top_k * 2,
                similarity_threshold=self.low_threshold
            )
            
            # 결과가 없으면 더 낮은 임계값으로 재시도
            if not search_results:
                logger.info("🔍 재검색 - 더 낮은 임계값으로 시도...")
                search_results = await vector_service.similarity_search(
                    session=db_session,
                    query=query,
                    user_id=user_id,
                    limit=self.top_k,
                    similarity_threshold=self.ultra_low_threshold
                )
                
            logger.info(f"📊 벡터 검색 결과: {len(search_results)}개 문서 발견")
            return search_results
            
        except Exception as search_error:
            logger.error(f"❌ 벡터 검색 실패: {search_error}")
            return []

    async def _supplement_with_hybrid_search(
        self, 
        db_session, 
        query: str, 
        user_id: int, 
        existing_results: List
    ) -> List:
        """하이브리드 검색으로 결과 보완"""
        logger.info("🔍 벡터 검색 결과 부족, 하이브리드 검색 시도...")
        
        try:
            hybrid_results = await vector_service.hybrid_search(
                session=db_session,
                query=query,
                user_id=user_id,
                limit=self.top_k,
                similarity_threshold=0.2,
                keyword_boost=0.2
            )
            logger.info(f"📊 하이브리드 검색 결과: {len(hybrid_results)}개 문서 발견")
            
            # 기존 결과와 합치되, 중복 제거
            existing_ids = {doc.id for doc, _ in existing_results}
            for doc, score in hybrid_results:
                if doc.id not in existing_ids:
                    existing_results.append((doc, score))
                    existing_ids.add(doc.id)
                    
        except Exception as e:
            logger.warning(f"⚠️ 하이브리드 검색 실패: {e}")
            
        return existing_results

    def _convert_search_results(
        self, 
        search_results: List, 
        user_id: int
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """검색 결과를 기존 포맷으로 변환"""
        results = []
        filtered_count = 0
        
        for i, (document, score) in enumerate(search_results[:self.top_k]):
            # 사용자 ID 검증
            if document.user_id != user_id:
                logger.warning(
                    f"⚠️ 다른 사용자의 문서 필터링됨 - "
                    f"doc_user_id: {document.user_id}, current_user_id: {user_id}"
                )
                filtered_count += 1
                continue
            
            snippet = document.content[:160].replace("\n", " ")
            metadata = {
                "title": document.title or "(제목없음)",
                "url": document.url or "",
                "source_id": document.source_id,
                "source_type": document.source_type,
                "keywords": document.keywords or [],
                "score": score,
                "user_id": document.user_id
            }
            results.append((snippet, metadata))
            logger.debug(
                f"📄 문서 {len(results)}: {metadata['title'][:30]} "
                f"(점수: {score:.3f}, user_id: {document.user_id})"
            )
        
        if filtered_count > 0:
            logger.warning(f"⚠️ 총 {filtered_count}개 다른 사용자 문서가 필터링되었습니다")

        logger.info(f"✅ 컨텍스트 검색 완료 - 최종 결과: {len(results)}개 문서")
        return results


# 싱글톤 인스턴스
rag_search_service = RAGSearchService() 