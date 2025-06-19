"""
벡터 검색 서비스

PostgreSQL pgvector를 사용하여 ChromaDB를 대체하는 벡터 검색 서비스입니다.
임베딩 생성, 벡터 저장, 유사도 검색 등의 기능을 제공합니다.
"""
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from loguru import logger

from app.core.config import settings
from app.repositories.vector_repository import VectorRepository
from app.models.chat import DocumentVector


class VectorService:
    """벡터 검색 서비스"""

    def __init__(self):
        """벡터 서비스 초기화"""
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBED_MODEL or "text-embedding-3-small"
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        logger.info("🚀 벡터 서비스 초기화 완료")

    async def save_document(  # pylint: disable=too-many-locals
        self,
        session: AsyncSession,
        user_id: int,
        source_data: Dict[str, Any],
        content: str,
        **kwargs
    ) -> List[DocumentVector]:
        """
        문서를 청크로 분할하고 임베딩하여 저장합니다.

        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID
            source_data: 소스 정보 (source_id, source_type 포함)
            content: 문서 내용
            **kwargs: 추가 옵션들
                title: 문서 제목
                url: 원본 URL
                keywords: 키워드 목록
                summary: 문서 요약
                extra_metadata: 추가 메타데이터

        Returns:
            저장된 DocumentVector 객체들의 리스트
        """
        source_id = source_data.get('source_id')
        source_type = source_data.get('source_type')
        title = kwargs.get('title')
        url = kwargs.get('url')
        keywords = kwargs.get('keywords')
        summary = kwargs.get('summary')
        extra_metadata = kwargs.get('extra_metadata')

        logger.info(f"📝 문서 처리 시작 - user_id: {user_id}, source_id: {source_id}")

        # 1. 텍스트를 청크로 분할
        chunks = self.text_splitter.split_text(content)
        logger.info(f"📄 텍스트 분할 완료 - 청크 수: {len(chunks)}")

        if not chunks:
            logger.warning("분할된 청크가 없습니다")
            return []

        # 2. 각 청크에 대해 임베딩 생성
        logger.info("🧠 임베딩 생성 중...")
        embeddings = await self.embeddings.aembed_documents(chunks)
        logger.info(f"✅ 임베딩 생성 완료 - 벡터 수: {len(embeddings)}")

        # 3. 벡터 저장소에 저장
        saved_vectors = await VectorRepository.save_document_vectors(
            session=session,
            user_id=user_id,
            source_id=source_id,
            source_type=source_type,
            chunks=chunks,
            embeddings=embeddings,
            title=title,
            url=url,
            keywords=keywords,
            summary=summary,
            embedding_model=self.embeddings.model,
            chunk_size=getattr(self.text_splitter, 'chunk_size', 1000),
            chunk_overlap=getattr(self.text_splitter, 'chunk_overlap', 200),
            extra_metadata=extra_metadata
        )

        logger.info(f"🎉 문서 저장 완료 - user_id: {user_id}, source_id: {source_id}")
        return saved_vectors

    async def save_document_chunk(
        self,
        session: AsyncSession,
        user_id: int,
        source_data: Dict[str, Any],
        content: str,
        chunk_index: int = 0,
        **kwargs
    ) -> List[DocumentVector]:
        """
        이미 분할된 단일 청크를 임베딩하여 저장합니다. (중복 분할 방지)

        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID
            source_data: 소스 정보 (source_id, source_type 포함)
            content: 청크 내용 (이미 분할된 텍스트)
            chunk_index: 청크 인덱스
            **kwargs: 추가 옵션들
                title: 문서 제목
                url: 원본 URL
                keywords: 키워드 목록
                summary: 문서 요약
                extra_metadata: 추가 메타데이터

        Returns:
            저장된 DocumentVector 객체들의 리스트
        """
        source_id = source_data.get('source_id')
        source_type = source_data.get('source_type')
        title = kwargs.get('title')
        url = kwargs.get('url')
        keywords = kwargs.get('keywords')
        summary = kwargs.get('summary')
        extra_metadata = kwargs.get('extra_metadata')

        logger.info(f"📝 청크 처리 시작 - user_id: {user_id}, source_id: {source_id}, chunk_index: {chunk_index}")

        if not content or not content.strip():
            logger.warning("빈 청크 내용입니다")
            return []

        # 1. 단일 청크에 대해 임베딩 생성
        logger.info("🧠 임베딩 생성 중...")
        embedding = await self.embeddings.aembed_query(content)  # 단일 텍스트용 메서드 사용
        logger.info(f"✅ 임베딩 생성 완료 - 차원: {len(embedding)}")

        # 2. 단일 벡터로 저장 (기존 삭제 없이)
        saved_vectors = await VectorRepository.save_single_document_vector(
            session=session,
            user_id=user_id,
            source_id=source_id,
            source_type=source_type,
            chunk_index=chunk_index,
            content=content,
            embedding=embedding,
            title=title,
            url=url,
            keywords=keywords,
            summary=summary,
            embedding_model=self.embeddings.model,
            chunk_size=getattr(self.text_splitter, 'chunk_size', 1000),
            chunk_overlap=getattr(self.text_splitter, 'chunk_overlap', 200),
            extra_metadata=extra_metadata
        )

        logger.info(f"🎉 청크 저장 완료 - user_id: {user_id}, source_id: {source_id}, chunk_index: {chunk_index}")
        return saved_vectors

    async def similarity_search(
        self,
        session: AsyncSession,
        query: str,
        **kwargs
    ) -> List[Tuple[DocumentVector, float]]:
        """
        벡터 유사도 검색을 수행합니다.

        Args:
            session: 데이터베이스 세션
            query: 검색 쿼리
            **kwargs: 검색 옵션들
                user_id: 특정 사용자의 문서만 검색
                source_types: 특정 소스 타입만 검색
                limit: 최대 결과 수 (기본값: 10)
                similarity_threshold: 유사도 임계값 (기본값: 0.7)

        Returns:
            (DocumentVector, similarity_score) 튜플들의 리스트
        """
        user_id = kwargs.get('user_id')
        source_types = kwargs.get('source_types')
        limit = kwargs.get('limit', 10)
        similarity_threshold = kwargs.get('similarity_threshold', 0.7)

        logger.info(f"🔍 벡터 검색 시작 - query: '{query[:50]}...', user_id: {user_id}")
        logger.info(f"📊 검색 설정 - limit: {limit}, threshold: {similarity_threshold}")

        try:
            # 쿼리를 임베딩으로 변환
            logger.info("🧠 쿼리 임베딩 생성 중...")
            query_embedding = await self.embeddings.aembed_query(query)
            
            # 임베딩 검증
            embedding_magnitude = sum(abs(x) for x in query_embedding)
            logger.info(f"✅ 쿼리 임베딩 생성 완료 - 차원: {len(query_embedding)}, 크기: {embedding_magnitude:.6f}")
            
            if embedding_magnitude < 0.001:
                logger.warning("⚠️ 쿼리 임베딩이 너무 작습니다 (거의 0 벡터)")
                
            # 벡터 유사도 검색 수행
            logger.info("🔍 데이터베이스 벡터 검색 수행 중...")
            results = await VectorRepository.similarity_search(
                session=session,
                query_embedding=query_embedding,
                user_id=user_id,
                source_types=source_types,
                limit=limit,
                similarity_threshold=similarity_threshold
            )

            if results:
                logger.info(f"✅ 벡터 검색 성공 - 결과 수: {len(results)}")
                for i, (doc, score) in enumerate(results[:3]):  # 상위 3개만 로깅
                    logger.info(f"  🔍 {i+1}. '{doc.title[:30]}...' (점수: {score:.3f})")
            else:
                logger.warning("⚠️ 벡터 검색 결과가 없습니다")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 벡터 검색 중 오류 발생: {e}")
            return []

    async def hybrid_search(
        self,
        session: AsyncSession,
        query: str,
        **kwargs
    ) -> List[Tuple[DocumentVector, float]]:
        """
        하이브리드 검색 (벡터 + 키워드)을 수행합니다.

        Args:
            session: 데이터베이스 세션
            query: 검색 쿼리
            **kwargs: 검색 옵션들
                user_id: 특정 사용자의 문서만 검색
                source_types: 특정 소스 타입만 검색
                keywords: 특정 키워드가 포함된 문서만 검색
                limit: 최대 결과 수 (기본값: 10)
                similarity_threshold: 유사도 임계값 (기본값: 0.7)
                keyword_boost: 키워드 매칭 시 추가 점수 (기본값: 0.1)

        Returns:
            (DocumentVector, combined_score) 튜플들의 리스트
        """
        user_id = kwargs.get('user_id')
        source_types = kwargs.get('source_types')
        keywords = kwargs.get('keywords')
        limit = kwargs.get('limit', 10)
        similarity_threshold = kwargs.get('similarity_threshold', 0.7)
        keyword_boost = kwargs.get('keyword_boost', 0.1)

        logger.info(f"🔍 하이브리드 검색 시작 - query: {query[:50]}...")

        # 쿼리를 임베딩으로 변환
        query_embedding = await self.embeddings.aembed_query(query)

        # 하이브리드 검색 수행
        results = await VectorRepository.hybrid_search(
            session=session,
            query_embedding=query_embedding,
            query_text=query,
            user_id=user_id,
            source_types=source_types,
            keywords=keywords,
            limit=limit,
            similarity_threshold=similarity_threshold,
            keyword_boost=keyword_boost
        )

        logger.info(f"✅ 하이브리드 검색 완료 - 결과 수: {len(results)}")
        return results

    async def delete_document(
        self,
        session: AsyncSession,
        user_id: int,
        source_id: str,
        source_type: str
    ) -> int:
        """
        특정 문서의 모든 벡터를 삭제합니다.

        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID
            source_id: 원본 문서 ID
            source_type: 소스 타입

        Returns:
            삭제된 벡터 수
        """
        deleted_count = await VectorRepository.delete_documents_by_source(
            session=session,
            user_id=user_id,
            source_id=source_id,
            source_type=source_type
        )

        log_msg = (
            f"🗑️ 문서 삭제 완료 - user_id: {user_id}, "
            f"source_id: {source_id}, 삭제 수: {deleted_count}"
        )
        logger.info(log_msg)
        return deleted_count

    async def get_user_document_stats(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """
        사용자의 문서 통계를 조회합니다.

        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID

        Returns:
            사용자 문서 통계 딕셔너리
        """
        # 전체 문서 수
        total_count = await VectorRepository.get_user_document_count(session, user_id)

        # 북마크 문서 수
        bookmark_count = await VectorRepository.get_user_document_count(
            session, user_id, source_type="bookmark"
        )

        # 웹 문서 수
        web_count = await VectorRepository.get_user_document_count(
            session, user_id, source_type="web"
        )

        return {
            "user_id": user_id,
            "total_documents": total_count,
            "bookmark_documents": bookmark_count,
            "web_documents": web_count,
            "other_documents": total_count - bookmark_count - web_count
        }

    def format_search_results_for_rag(
        self,
        search_results: List[Tuple[DocumentVector, float]]
    ) -> List[Dict[str, Any]]:
        """
        검색 결과를 RAG 시스템에서 사용할 수 있는 형식으로 변환합니다.

        Args:
            search_results: 벡터 검색 결과

        Returns:
            RAG 시스템용 검색 결과 리스트
        """
        formatted_results = []

        for document, score in search_results:
            snippet = (
                document.content[:200] + "..."
                if len(document.content) > 200
                else document.content
            )

            formatted_result = {
                "source_id": document.source_id,
                "source_type": document.source_type,
                "title": document.title,
                "url": document.url,
                "snippet": snippet,
                "content": document.content,
                "keywords": document.keywords or [],
                "score": score,
                "chunk_index": document.chunk_index,
                "metadata": {
                    "user_id": document.user_id,
                    "embedding_model": document.embedding_model,
                    "created_at": document.created_at.isoformat(),
                    "extra_metadata": document.extra_metadata or {}
                }
            }
            formatted_results.append(formatted_result)

        return formatted_results


# 싱글턴 인스턴스
vector_service = VectorService()
