"""
벡터 저장소 Repository

PostgreSQL의 pgvector 확장을 사용하여 벡터 임베딩을 저장하고 검색하는 Repository입니다.
기존 ChromaDB의 기능을 PostgreSQL로 대체합니다.
"""
import hashlib
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from sqlmodel import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.chat import (
    DocumentVector, DocumentVectorCreate, VectorSearchResult, VectorSearchRequest
)


class VectorRepository:
    """벡터 저장소 데이터 접근을 처리하는 Repository"""
    
    @staticmethod
    def _generate_content_hash(content: str) -> str:
        """내용의 해시값을 생성합니다."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    @staticmethod
    async def save_document_vectors(
        session: AsyncSession,
        user_id: int,
        source_id: str,
        source_type: str,
        chunks: List[str],
        embeddings: List[List[float]],
        title: Optional[str] = None,
        url: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        summary: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentVector]:
        """
        문서 벡터들을 저장합니다.
        
        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID
            source_id: 원본 문서 ID
            source_type: 소스 타입 (bookmark, web, document 등)
            chunks: 분할된 텍스트 청크들
            embeddings: 각 청크의 임베딩 벡터들
            title: 문서 제목
            url: 원본 URL
            keywords: 키워드 목록
            summary: 문서 요약
            embedding_model: 사용된 임베딩 모델
            chunk_size: 청크 크기
            chunk_overlap: 청크 겹침
            extra_metadata: 추가 메타데이터
            
        Returns:
            저장된 DocumentVector 객체들의 리스트
        """
        if len(chunks) != len(embeddings):
            raise ValueError("청크 수와 임베딩 수가 일치하지 않습니다")
        
        # 기존 동일 소스 문서 삭제 로직 제거 - 상위 레벨에서 관리
        # await VectorRepository.delete_documents_by_source(
        #     session, user_id, source_id, source_type
        # )
        
        saved_vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            content_hash = VectorRepository._generate_content_hash(chunk)
            
            document_vector = DocumentVector(
                user_id=user_id,
                source_id=source_id,
                source_type=source_type,
                chunk_index=i,
                content=chunk,
                content_hash=content_hash,
                embedding=embedding,
                title=title,
                url=url,
                keywords=keywords,
                summary=summary,
                embedding_model=embedding_model,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                extra_metadata=extra_metadata
            )
            
            session.add(document_vector)
            saved_vectors.append(document_vector)
        
        await session.commit()
        for vector in saved_vectors:
            await session.refresh(vector)
        
        logger.info(f"📚 벡터 문서 저장 완료 - user_id: {user_id}, source_id: {source_id}, 청크 수: {len(saved_vectors)}")
        return saved_vectors
    
    @staticmethod
    async def save_single_document_vector(
        session: AsyncSession,
        user_id: int,
        source_id: str,
        source_type: str,
        chunk_index: int,
        content: str,
        embedding: List[float],
        title: Optional[str] = None,
        url: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        summary: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentVector]:
        """
        단일 문서 벡터를 저장합니다. (기존 삭제 없이)
        
        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID
            source_id: 원본 문서 ID
            source_type: 소스 타입
            chunk_index: 청크 인덱스
            content: 청크 내용
            embedding: 임베딩 벡터
            title: 문서 제목
            url: 원본 URL
            keywords: 키워드 목록
            summary: 문서 요약
            embedding_model: 사용된 임베딩 모델
            chunk_size: 청크 크기
            chunk_overlap: 청크 겹침
            extra_metadata: 추가 메타데이터
            
        Returns:
            저장된 DocumentVector 객체 리스트 (단일 요소)
        """
        content_hash = VectorRepository._generate_content_hash(content)
        
        document_vector = DocumentVector(
            user_id=user_id,
            source_id=source_id,
            source_type=source_type,
            chunk_index=chunk_index,
            content=content,
            content_hash=content_hash,
            embedding=embedding,
            title=title,
            url=url,
            keywords=keywords,
            summary=summary,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            extra_metadata=extra_metadata
        )
        
        session.add(document_vector)
        await session.commit()
        await session.refresh(document_vector)
        
        logger.info(f"📝 단일 벡터 저장 완료 - user_id: {user_id}, source_id: {source_id}, chunk_index: {chunk_index}")
        return [document_vector]
    
    @staticmethod
    async def similarity_search(
        session: AsyncSession,
        query_embedding: List[float],
        user_id: Optional[int] = None,
        source_types: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Tuple[DocumentVector, float]]:
        """
        벡터 유사도 검색을 수행합니다.
        
        Args:
            session: 데이터베이스 세션
            query_embedding: 쿼리 임베딩 벡터
            user_id: 특정 사용자의 문서만 검색 (None이면 전체 검색)
            source_types: 특정 소스 타입만 검색
            limit: 최대 결과 수
            similarity_threshold: 유사도 임계값
            
        Returns:
            (DocumentVector, similarity_score) 튜플들의 리스트
        """
        # pgvector의 cosine distance를 사용한 유사도 검색
        # cosine distance = 1 - cosine similarity
        # 따라서 distance가 작을수록 유사도가 높음
        
        query = select(
            DocumentVector,
            (1 - DocumentVector.embedding.cosine_distance(query_embedding)).label("similarity_score")
        ).where(
            (1 - DocumentVector.embedding.cosine_distance(query_embedding)) >= similarity_threshold
        )
        
        # 사용자별 필터링
        if user_id:
            query = query.where(DocumentVector.user_id == user_id)
        
        # 소스 타입별 필터링
        if source_types:
            query = query.where(DocumentVector.source_type.in_(source_types))
        
        # 유사도 순으로 정렬 및 제한
        query = query.order_by(
            (1 - DocumentVector.embedding.cosine_distance(query_embedding)).desc()
        ).limit(limit)
        
        result = await session.execute(query)
        results = result.all()
        
        logger.info(f"🔍 벡터 유사도 검색 완료 - 결과 수: {len(results)}, user_id: {user_id}")
        return [(row[0], float(row[1])) for row in results]
    
    @staticmethod
    async def hybrid_search(
        session: AsyncSession,
        query_embedding: List[float],
        query_text: Optional[str] = None,
        user_id: Optional[int] = None,
        source_types: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
        keyword_boost: float = 0.1
    ) -> List[Tuple[DocumentVector, float]]:
        """
        하이브리드 검색 (벡터 + 키워드)을 수행합니다.
        
        Args:
            session: 데이터베이스 세션
            query_embedding: 쿼리 임베딩 벡터
            query_text: 키워드 검색용 텍스트
            user_id: 특정 사용자의 문서만 검색
            source_types: 특정 소스 타입만 검색
            keywords: 특정 키워드가 포함된 문서만 검색
            limit: 최대 결과 수
            similarity_threshold: 유사도 임계값
            keyword_boost: 키워드 매칭 시 추가 점수
            
        Returns:
            (DocumentVector, combined_score) 튜플들의 리스트
        """
        base_similarity = (1 - DocumentVector.embedding.cosine_distance(query_embedding))
        
        # 키워드 매칭 점수 계산
        keyword_score = 0.0
        if query_text:
            # PostgreSQL의 텍스트 검색 기능 사용
            keyword_score = text("ts_rank(to_tsvector('english', content), to_tsquery('english', :query_text))").bindparam(query_text=query_text)
        
        if keywords:
            # JSONB 키워드 배열에서 매칭되는 키워드 수에 따른 가중치
            keyword_match_score = text("jsonb_array_length(keywords) * 0.1").label("keyword_match_score")
        
        # 최종 점수 = 벡터 유사도 + 키워드 점수
        combined_score = base_similarity + keyword_boost * keyword_score if query_text else base_similarity
        
        query = select(
            DocumentVector,
            combined_score.label("combined_score")
        ).where(
            base_similarity >= similarity_threshold
        )
        
        # 필터링 조건들
        if user_id:
            query = query.where(DocumentVector.user_id == user_id)
        
        if source_types:
            query = query.where(DocumentVector.source_type.in_(source_types))
        
        if keywords:
            # JSONB 배열에서 키워드 검색
            for keyword in keywords:
                query = query.where(DocumentVector.keywords.contains([keyword]))
        
        # 점수 순으로 정렬 및 제한
        query = query.order_by(combined_score.desc()).limit(limit)
        
        result = await session.execute(query)
        results = result.all()
        
        logger.info(f"🔍 하이브리드 검색 완료 - 결과 수: {len(results)}, user_id: {user_id}")
        return [(row[0], float(row[1])) for row in results]
    
    @staticmethod
    async def get_documents_by_source(
        session: AsyncSession,
        user_id: int,
        source_id: str,
        source_type: str
    ) -> List[DocumentVector]:
        """특정 소스의 모든 문서 벡터를 조회합니다."""
        stmt = select(DocumentVector).where(
            and_(
                DocumentVector.user_id == user_id,
                DocumentVector.source_id == source_id,
                DocumentVector.source_type == source_type
            )
        ).order_by(DocumentVector.chunk_index.asc())
        
        result = await session.execute(stmt)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_documents_by_user(
        session: AsyncSession,
        user_id: int,
        source_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[DocumentVector]:
        """
        특정 사용자의 모든 문서 벡터를 조회합니다.
        
        Args:
            session: 데이터베이스 세션
            user_id: 사용자 ID (int)
            source_type: 특정 소스 타입만 조회 (선택적)
            limit: 최대 결과 수 (선택적)
            
        Returns:
            DocumentVector 객체들의 리스트
        """
        stmt = select(DocumentVector).where(DocumentVector.user_id == user_id)
        
        if source_type:
            stmt = stmt.where(DocumentVector.source_type == source_type)
        
        # 생성 시간 역순으로 정렬 (최신 순)
        stmt = stmt.order_by(DocumentVector.created_at.desc())
        
        if limit:
            stmt = stmt.limit(limit)
        
        result = await session.execute(stmt)
        documents = list(result.scalars().all())
        
        logger.info(f"📚 사용자 문서 조회 완료 - user_id: {user_id}, source_type: {source_type}, 결과 수: {len(documents)}")
        return documents
    
    @staticmethod
    async def delete_documents_by_source(
        session: AsyncSession,
        user_id: int,
        source_id: str,
        source_type: str
    ) -> int:
        """특정 소스의 모든 문서 벡터를 삭제합니다."""
        # 먼저 삭제할 문서들을 조회
        docs_to_delete = await VectorRepository.get_documents_by_source(
            session, user_id, source_id, source_type
        )
        
        # 삭제 실행
        for doc in docs_to_delete:
            await session.delete(doc)
        
        await session.commit()
        
        logger.info(f"🗑️ 벡터 문서 삭제 완료 - user_id: {user_id}, source_id: {source_id}, 삭제 수: {len(docs_to_delete)}")
        return len(docs_to_delete)
    
    @staticmethod
    async def get_user_document_count(
        session: AsyncSession,
        user_id: int,
        source_type: Optional[str] = None
    ) -> int:
        """사용자의 문서 수를 조회합니다."""
        query = select(DocumentVector).where(DocumentVector.user_id == user_id)
        
        if source_type:
            query = query.where(DocumentVector.source_type == source_type)
        
        result = await session.execute(query)
        return len(list(result.scalars().all()))
    
    @staticmethod
    async def get_vector_stats(session: AsyncSession) -> Dict[str, Any]:
        """벡터 저장소 통계를 조회합니다."""
        # 총 벡터 수
        total_count_query = select(DocumentVector)
        total_result = await session.execute(total_count_query)
        total_vectors = len(list(total_result.scalars().all()))
        
        # 고유 사용자 수
        unique_users_query = select(DocumentVector.user_id).distinct()
        users_result = await session.execute(unique_users_query)
        unique_users = len(list(users_result.scalars().all()))
        
        # 소스 타입별 통계
        source_types_query = select(DocumentVector.source_type).distinct()
        sources_result = await session.execute(source_types_query)
        unique_sources = len(list(sources_result.scalars().all()))
        
        return {
            "total_vectors": total_vectors,
            "unique_users": unique_users,
            "unique_sources": unique_sources,
            "last_updated": datetime.utcnow()
        } 