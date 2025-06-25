"""
RAG (Retrieval-Augmented Generation) 검색 서비스

사용자 쿼리에 대해 PostgreSQL 벡터 데이터베이스에서 관련 문서를 검색합니다.

## 주요 기능
- 청크 집계 벡터 검색: 같은 문서의 여러 청크를 결합하여 더 풍부한 컨텍스트 제공
- 하이브리드 검색: 벡터 검색 결과가 부족할 때 키워드 검색으로 보완
- 문서 중복 제거: source_id 기반으로 중복 문서 제거
- 다단계 임계값: 낮은 임계값으로 재검색하여 결과 보완

## 검색 과정
1. 청크 집계 벡터 검색 (문서당 최대 3개 청크 결합)
2. 결과 부족 시 낮은 임계값으로 재검색
3. 여전히 부족할 때 하이브리드 검색으로 보완
4. 최종 결과를 RAG 시스템용 포맷으로 변환
"""

from typing import Dict, Any, List, Tuple
from loguru import logger

from app.core.database import get_async_session
from app.services.vector_service import vector_service
from app.repositories.vector_repository import VectorRepository


class RAGSearchService:
    """RAG 검색을 담당하는 서비스 클래스"""
    
    def __init__(self, top_k: int = 10, max_chunks_per_doc: int = 3):
        """
        RAG 검색 서비스 초기화
        
        Args:
            top_k: 검색할 최대 문서 수
            max_chunks_per_doc: 문서당 최대 청크 수
                - 2: 빠른 처리, 핵심 정보만
                - 3: 균형잡힌 설정 (기본값, 권장)
                - 4-5: 더 풍부한 컨텍스트, 처리 시간 증가
                - 6+: 노이즈 증가 가능성, 토큰 제한 주의
        """
        self.top_k = top_k
        self.max_chunks_per_doc = max_chunks_per_doc
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
                                
                # 결과 변환
                return self._convert_search_results(search_results)
                
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
        logger.info(f"🔍 청크 집계 벡터 검색 실행 - threshold: {self.low_threshold}, limit: {self.top_k}")
        
        try:
            # 청크 집계 검색 실행 (문서별로 여러 청크를 결합)
            search_results = await vector_service.similarity_search_with_chunk_aggregation(
                session=db_session,
                query=query,
                user_id=user_id,
                limit=self.top_k,
                similarity_threshold=self.low_threshold,
                max_chunks_per_doc=self.max_chunks_per_doc,
                search_limit_multiplier=4  # 더 많은 결과에서 집계
            )
            
            # 결과가 없으면 더 낮은 임계값으로 재시도
            if not search_results:
                logger.info("🔍 재검색 - 더 낮은 임계값으로 시도...")
                search_results = await vector_service.similarity_search_with_chunk_aggregation(
                    session=db_session,
                    query=query,
                    user_id=user_id,
                    limit=self.top_k,
                    similarity_threshold=self.ultra_low_threshold,
                    max_chunks_per_doc=self.max_chunks_per_doc,
                    search_limit_multiplier=4
                )
                
            logger.info(f"📊 청크 집계 검색 결과: {len(search_results)}개 문서 발견")
            return search_results
            
        except Exception as search_error:
            logger.error(f"❌ 벡터 검색 실패: {search_error}")
            return []


    def _convert_search_results(
        self, 
        search_results: List
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """검색 결과를 기존 포맷으로 변환 (집계된 결과 지원, 요약과 메모 포함)"""
        results = []
        
        for i, result in enumerate(search_results):
            # 집계된 결과인지 확인 (Dict 형태)
            if isinstance(result, dict):
                # 집계된 결과 처리
                metadata = {
                    "title": result["title"] or "(제목없음)",
                    "url": result["url"] or "",
                    "source_id": result["source_id"],
                    "source_type": result["source_type"],
                    "keywords": result["keywords"] or [],
                    "score": result["average_score"],
                    "primary_score": result["primary_score"],
                    "chunk_count": result["chunk_count"],
                    "total_chunks_found": result["total_chunks_found"],
                    "top_chunks": result["top_chunks"],
                    "user_id": result["metadata"]["user_id"]
                }
                content = result["combined_content"]
                
                logger.debug(
                    f"📄 집계 문서 {len(results)+1}: {metadata['title'][:30]} "
                    f"(평균점수: {result['average_score']:.3f}, 청크수: {result['chunk_count']}, "
                    f"user_id: {result['metadata']['user_id']})"
                )
                
            else:
                # 기존 튜플 형태 결과 처리 (DocumentVector, score)
                document, score = result
                
                metadata = {
                    "title": document.title or "(제목없음)",
                    "url": document.url or "",
                    "source_id": document.source_id,
                    "source_type": document.source_type,
                    "keywords": document.keywords or [],
                    "score": score,
                    "user_id": document.user_id
                }
                content = document.content
                
                logger.debug(
                    f"📄 단일 문서 {len(results)+1}: {metadata['title'][:30]} "
                    f"(점수: {score:.3f}, 내용길이: {len(document.content)}자, user_id: {document.user_id})"
                )
            
            results.append((content, metadata))

        logger.info(f"✅ 컨텍스트 검색 완료 - 최종 결과: {len(results)}개 문서")
        return results


# 싱글톤 인스턴스
rag_search_service = RAGSearchService()
