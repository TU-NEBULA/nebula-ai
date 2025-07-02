"""
벡터 검색 서비스

PostgreSQL pgvector를 사용하여 ChromaDB를 대체하는 벡터 검색 서비스입니다.
임베딩 생성, 벡터 저장, 유사도 검색 등의 기능을 제공합니다.

## 주요 기능

### 기본 검색
- similarity_search: 기본 벡터 유사도 검색 (청크별 개별 결과)

### 중복 제거 검색
- similarity_search_with_deduplication: 문서별 중복 제거된 검색 결과
  같은 문서의 여러 청크 중 가장 높은 유사도를 가진 청크만 반환

### 청크 집계 검색  
- similarity_search_with_chunk_aggregation: 문서별 청크 집계 검색
  같은 문서의 상위 청크들을 결합하여 더 풍부한 컨텍스트 제공

## 사용 예시

```python
# 기본 검색 (청크별 개별 결과)
results = await vector_service.similarity_search(session, query, user_id=user_id)

# 중복 제거 검색 (문서별 최고 점수 청크만)
results = await vector_service.similarity_search_with_deduplication(
    session, query, user_id=user_id, limit=10
)

# 청크 집계 검색 (문서별 여러 청크 결합)
results = await vector_service.similarity_search_with_chunk_aggregation(
    session, query, user_id=user_id, limit=5, max_chunks_per_doc=3
)
```
"""
import time
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from loguru import logger

from app.core.config import settings
from app.core.monitoring import prometheus_metrics
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
        start_time = time.time()
        source_id = source_data.get('source_id')
        source_type = source_data.get('source_type')
        title = kwargs.get('title')
        url = kwargs.get('url')
        keywords = kwargs.get('keywords')
        summary = kwargs.get('summary')
        extra_metadata = kwargs.get('extra_metadata')

        logger.info(f"📝 문서 처리 시작 - user_id: {user_id}, source_id: {source_id}")

        try:
            # 벡터 작업 시작 메트릭
            prometheus_metrics.increment_vector_operations("save_document", "started")

            # 1. 텍스트를 청크로 분할
            chunks = self.text_splitter.split_text(content)
            logger.info(f"📄 텍스트 분할 완료 - 청크 수: {len(chunks)}")

            if not chunks:
                logger.warning("분할된 청크가 없습니다")
                prometheus_metrics.increment_vector_operations("save_document", "no_chunks")
                return []

            # 2. 각 청크에 대해 임베딩 생성
            logger.info("🧠 임베딩 생성 중...")
            embedding_start = time.time()
            embeddings = await self.embeddings.aembed_documents(chunks)
            embedding_duration = time.time() - embedding_start
            logger.info(f"✅ 임베딩 생성 완료 - 벡터 수: {len(embeddings)}")
            
            # OpenAI API 호출 시간 기록
            prometheus_metrics.record_external_api_call("openai", "embeddings", embedding_duration)

            # 3. 벡터 저장소에 저장
            db_start = time.time()
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
            db_duration = time.time() - db_start
            
            # 데이터베이스 저장 시간 기록
            prometheus_metrics.record_database_query("insert", "document_vectors", db_duration)

            # 성공 메트릭 기록
            total_duration = time.time() - start_time
            prometheus_metrics.increment_vector_operations("save_document", "success")

            logger.info(f"🎉 문서 저장 완료 - user_id: {user_id}, source_id: {source_id}")
            return saved_vectors

        except Exception as e:
            # 실패 메트릭 기록
            total_duration = time.time() - start_time
            prometheus_metrics.increment_vector_operations("save_document", "error")
            logger.error(f"❌ 문서 저장 실패 - user_id: {user_id}, source_id: {source_id}, 오류: {e}")
            raise

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
        start_time = time.time()
        user_id = kwargs.get('user_id')
        source_types = kwargs.get('source_types')
        limit = kwargs.get('limit', 10)
        similarity_threshold = kwargs.get('similarity_threshold', 0.7)

        logger.info(f"🔍 벡터 검색 시작 - query: '{query[:50]}...', user_id: {user_id}")
        logger.info(f"📊 검색 설정 - limit: {limit}, threshold: {similarity_threshold}")

        try:
            # 벡터 검색 시작 메트릭
            prometheus_metrics.increment_vector_operations("similarity_search", "started")

            # 쿼리를 임베딩으로 변환
            logger.info("🧠 쿼리 임베딩 생성 중...")
            embedding_start = time.time()
            query_embedding = await self.embeddings.aembed_query(query)
            embedding_duration = time.time() - embedding_start
            
            # OpenAI API 호출 시간 기록
            prometheus_metrics.record_external_api_call("openai", "query_embedding", embedding_duration)
            
            # 임베딩 검증
            embedding_magnitude = sum(abs(x) for x in query_embedding)
            logger.info(f"✅ 쿼리 임베딩 생성 완료 - 차원: {len(query_embedding)}, 크기: {embedding_magnitude:.6f}")
            
            if embedding_magnitude < 0.001:
                logger.warning("⚠️ 쿼리 임베딩이 너무 작습니다 (거의 0 벡터)")
                
            # 벡터 유사도 검색 수행
            logger.info("🔍 데이터베이스 벡터 검색 수행 중...")
            db_start = time.time()
            results = await VectorRepository.similarity_search(
                session=session,
                query_embedding=query_embedding,
                user_id=user_id,
                source_types=source_types,
                limit=limit,
                similarity_threshold=similarity_threshold
            )
            db_duration = time.time() - db_start
            
            # 데이터베이스 검색 시간 기록
            prometheus_metrics.record_database_query("vector_search", "document_vectors", db_duration)

            # 성공 메트릭 기록
            total_duration = time.time() - start_time
            prometheus_metrics.increment_vector_operations("similarity_search", "success")

            if results:
                logger.info(f"✅ 벡터 검색 성공 - 결과 수: {len(results)}")
                for i, (doc, score) in enumerate(results[:3]):  # 상위 3개만 로깅
                    logger.info(f"  🔍 {i+1}. '{doc.title[:30]}...' (점수: {score:.3f})")
            else:
                logger.warning("⚠️ 벡터 검색 결과가 없습니다")
                prometheus_metrics.increment_vector_operations("similarity_search", "no_results")
            
            return results
            
        except Exception as e:
            # 실패 메트릭 기록
            total_duration = time.time() - start_time
            prometheus_metrics.increment_vector_operations("similarity_search", "error")
            logger.error(f"❌ 벡터 검색 중 오류 발생: {e}")
            return []

    async def similarity_search_with_deduplication(
        self,
        session: AsyncSession,
        query: str,
        **kwargs
    ) -> List[Tuple[DocumentVector, float]]:
        """
        벡터 유사도 검색을 수행하고 문서별 중복을 제거합니다.
        같은 source_id의 청크들 중 가장 높은 유사도를 가진 청크만 반환합니다.

        Args:
            session: 데이터베이스 세션
            query: 검색 쿼리
            **kwargs: 검색 옵션들
                user_id: 특정 사용자의 문서만 검색
                source_types: 특정 소스 타입만 검색
                limit: 최대 결과 수 (기본값: 10)
                similarity_threshold: 유사도 임계값 (기본값: 0.7)
                search_limit_multiplier: 검색 확장 배수 (기본값: 3)

        Returns:
            (DocumentVector, similarity_score) 튜플들의 리스트 (문서별 중복 제거됨)
        """
        # 중복 제거를 위해 더 많은 결과를 가져옴
        search_limit_multiplier = kwargs.get('search_limit_multiplier', 3)
        original_limit = kwargs.get('limit', 10)
        expanded_limit = original_limit * search_limit_multiplier
        
        # 확장된 검색 수행
        expanded_kwargs = kwargs.copy()
        expanded_kwargs['limit'] = expanded_limit
        
        logger.info(f"🔍 중복 제거 벡터 검색 시작 - 확장 검색 limit: {expanded_limit}")
        
        # 기본 검색 수행
        raw_results = await self.similarity_search(session, query, **expanded_kwargs)
        
        if not raw_results:
            return []
        
        # 문서별 중복 제거 (가장 높은 점수의 청크만 유지)
        deduplicated_results = self._deduplicate_by_source(raw_results)
        
        # 원래 요청된 limit까지만 반환
        final_results = deduplicated_results[:original_limit]
        
        logger.info(f"✅ 중복 제거 완료 - 원본: {len(raw_results)}, 중복제거 후: {len(deduplicated_results)}, 최종: {len(final_results)}")
        
        return final_results

    def _deduplicate_by_source(
        self, 
        results: List[Tuple[DocumentVector, float]]
    ) -> List[Tuple[DocumentVector, float]]:
        """
        검색 결과에서 source_id별로 중복을 제거합니다.
        같은 source_id의 청크들 중 가장 높은 유사도를 가진 청크만 유지합니다.

        Args:
            results: 원본 검색 결과

        Returns:
            중복이 제거된 검색 결과
        """
        source_best = {}  # source_id -> (DocumentVector, score)
        
        for doc, score in results:
            source_key = f"{doc.source_type}:{doc.source_id}"
            
            if source_key not in source_best or score > source_best[source_key][1]:
                source_best[source_key] = (doc, score)
        
        # 점수 순으로 정렬하여 반환
        deduplicated_results = list(source_best.values())
        deduplicated_results.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"📝 문서별 중복 제거 - 고유 문서 수: {len(deduplicated_results)}")
        
        return deduplicated_results

    async def similarity_search_with_chunk_aggregation(
        self,
        session: AsyncSession,
        query: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        벡터 유사도 검색을 수행하고 같은 문서의 청크들을 집계합니다.
        
        Args:
            session: 데이터베이스 세션
            query: 검색 쿼리
            **kwargs: 검색 옵션들
                user_id: 특정 사용자의 문서만 검색
                source_types: 특정 소스 타입만 검색
                limit: 최대 결과 수 (기본값: 10)
                similarity_threshold: 유사도 임계값 (기본값: 0.7)
                search_limit_multiplier: 검색 확장 배수 (기본값: 5)
                max_chunks_per_doc: 문서당 최대 청크 수 (기본값: 3)

        Returns:
            문서별로 집계된 결과 리스트
        """
        # 청크 집계를 위해 더 많은 결과를 가져옴
        search_limit_multiplier = kwargs.get('search_limit_multiplier', 5)
        original_limit = kwargs.get('limit', 10)
        max_chunks_per_doc = kwargs.get('max_chunks_per_doc', 3)
        expanded_limit = original_limit * search_limit_multiplier
        
        # 확장된 검색 수행
        expanded_kwargs = kwargs.copy()
        expanded_kwargs['limit'] = expanded_limit
        
        logger.info(f"🔍 청크 집계 벡터 검색 시작 - 확장 검색 limit: {expanded_limit}")
        
        # 기본 검색 수행
        raw_results = await self.similarity_search(session, query, **expanded_kwargs)
        
        if not raw_results:
            return []
        
        # 문서별로 청크들을 그룹화하고 집계
        aggregated_results = self._aggregate_chunks_by_source(
            raw_results, 
            max_chunks_per_doc=max_chunks_per_doc
        )
        
        # 원래 요청된 limit까지만 반환
        final_results = aggregated_results[:original_limit]
        
        logger.info(f"✅ 청크 집계 완료 - 원본: {len(raw_results)}, 집계 후: {len(final_results)}")
        
        return final_results

    def _aggregate_chunks_by_source(
        self, 
        results: List[Tuple[DocumentVector, float]],
        max_chunks_per_doc: int = 3
    ) -> List[Dict[str, Any]]:
        """
        검색 결과를 문서별로 그룹화하고 청크들을 집계합니다.
        URL을 기반으로 그룹화하여 메모, 요약, 본문이 하나로 합쳐집니다.

        Args:
            results: 원본 검색 결과
            max_chunks_per_doc: 문서당 최대 청크 수

        Returns:
            문서별로 집계된 결과 (요약과 메모 포함)
        """
        source_groups = {}  # group_key -> [(DocumentVector, score), ...]
        
        # 문서별로 그룹화 (URL 기반으로 그룹화)
        for doc, score in results:
            # URL이 있으면 URL을 기준으로, 없으면 source_type:source_id로 그룹화
            if doc.url:
                group_key = f"url:{doc.url}"
            else:
                group_key = f"{doc.source_type}:{doc.source_id}"
            
            if group_key not in source_groups:
                source_groups[group_key] = []
            
            source_groups[group_key].append((doc, score))
        
        aggregated_results = []
        
        for group_key, chunks in source_groups.items():
            # 점수 순으로 정렬하고 상위 청크들만 선택
            chunks.sort(key=lambda x: x[1], reverse=True)
            
            # 많은 청크가 있을 때 로깅
            if len(chunks) > max_chunks_per_doc:
                primary_doc = chunks[0][0]
                logger.info(f"📊 문서 '{primary_doc.title[:30]}...'에서 {len(chunks)}개 청크 발견")
                logger.info(f"   📈 점수 범위: {chunks[0][1]:.3f} ~ {chunks[-1][1]:.3f}")
                logger.info(f"   ✂️ 상위 {max_chunks_per_doc}개 청크만 선택, {len(chunks) - max_chunks_per_doc}개 청크 제외")
                
                # 선택된 청크와 제외된 청크 점수 보여주기
                selected_scores = [score for _, score in chunks[:max_chunks_per_doc]]
                excluded_scores = [score for _, score in chunks[max_chunks_per_doc:]]
                logger.info(f"   ✅ 선택된 청크 점수: {selected_scores}")
                if excluded_scores:
                    logger.info(f"   ❌ 제외된 청크 점수: {excluded_scores[:5]}{'...' if len(excluded_scores) > 5 else ''}")
            
            top_chunks = chunks[:max_chunks_per_doc]
            
            # 대표 문서 (가장 높은 점수)
            primary_doc, primary_score = top_chunks[0]
            
            # 평균 점수 계산
            avg_score = sum(score for _, score in top_chunks) / len(top_chunks)
            
            # 문서들에서 요약과 메모 정보 수집
            document_summary = ""
            document_memo = ""
            content_chunks = []
            
            # 모든 청크에서 요약, 메모, 일반 내용 분류
            for doc, _ in top_chunks:
                # 제목에서 메모/요약 구분
                if doc.title and ("[메모]" in doc.title or "메모:" in doc.content):
                    # 메모 문서
                    if doc.summary:
                        document_memo += doc.summary + "\n"
                    if doc.content and not document_memo:
                        # content에서 메모 내용 추출
                        content_lines = doc.content.split('\n')
                        for line in content_lines:
                            if "메모:" in line:
                                document_memo += line.replace("메모:", "").strip() + "\n"
                            elif "사용자 메모:" in line:
                                document_memo += line.replace("사용자 메모:", "").strip() + "\n"
                
                elif doc.title and ("[요약]" in doc.title or "요약:" in doc.content):
                    # 요약 문서
                    if doc.summary:
                        document_summary += doc.summary + "\n"
                    if doc.content and not document_summary:
                        # content에서 요약 내용 추출
                        content_lines = doc.content.split('\n')
                        for line in content_lines:
                            if "요약:" in line:
                                document_summary += line.replace("요약:", "").strip() + "\n"
                            elif "문서 요약:" in line:
                                document_summary += line.replace("문서 요약:", "").strip() + "\n"
                
                else:
                    # 일반 컨텐츠 청크
                    content_chunks.append((doc, _))
                    
                    # 일반 문서에서도 summary와 extra_metadata 확인
                    if doc.summary and not document_summary:
                        document_summary = doc.summary
                    
                    if doc.extra_metadata and not document_memo:
                        document_memo = doc.extra_metadata.get('memo', '') or \
                                      doc.extra_metadata.get('note', '') or \
                                      doc.extra_metadata.get('description', '')
            
            # 정리
            document_summary = document_summary.strip()
            document_memo = document_memo.strip()
            
            # 청크 내용들을 결합 (일반 컨텐츠만)
            if content_chunks:
                combined_content = "\n\n".join([
                    f"[청크 {doc.chunk_index}] {doc.content}" 
                    for doc, _ in content_chunks
                ])
            else:
                # 일반 컨텐츠가 없으면 모든 청크 사용
                combined_content = "\n\n".join([
                    f"[청크 {doc.chunk_index}] {doc.content}" 
                    for doc, _ in top_chunks
                ])
            
            # 요약과 메모가 있으면 combined_content 앞에 추가
            content_parts = []
            
            if document_summary:
                content_parts.append(f"[문서 요약]\n{document_summary}")
                
            if document_memo:
                content_parts.append(f"[메모]\n{document_memo}")
                
            content_parts.append(f"[청크 내용]\n{combined_content}")
            
            final_combined_content = "\n\n".join(content_parts)
            
            # 원본 제목 찾기 (메모/요약이 아닌 것)
            original_title = primary_doc.title
            for doc, _ in chunks:
                if doc.title and not ("[메모]" in doc.title or "[요약]" in doc.title):
                    original_title = doc.title
                    break
            
            # 집계된 결과 생성
            aggregated_result = {
                "source_id": primary_doc.source_id,
                "source_type": primary_doc.source_type,
                "title": original_title,  # 원본 제목 사용
                "url": primary_doc.url,
                "keywords": primary_doc.keywords or [],
                "summary": document_summary,  # 수집된 문서 요약
                "memo": document_memo,        # 수집된 문서 메모
                "primary_score": primary_score,
                "average_score": avg_score,
                "chunk_count": len(top_chunks),
                "total_chunks_found": len(chunks),  # 실제 발견된 총 청크 수
                "combined_content": final_combined_content,  # 요약+메모+청크 내용
                "chunks_only_content": combined_content,      # 청크 내용만
                "top_chunks": [
                    {
                        "chunk_index": doc.chunk_index,
                        "content": doc.content,
                        "score": score,
                        "title": doc.title  # 개별 청크 제목도 포함
                    }
                    for doc, score in top_chunks
                ],
                "metadata": {
                    "user_id": primary_doc.user_id,
                    "embedding_model": primary_doc.embedding_model,
                    "created_at": primary_doc.created_at.isoformat(),
                    "extra_metadata": primary_doc.extra_metadata or {},
                    "group_key": group_key,  # 디버깅용
                    "has_memo": bool(document_memo),
                    "has_summary": bool(document_summary)
                }
            }
            
            aggregated_results.append(aggregated_result)
            
            # 요약과 메모 포함 로깅
            logger.info(f"📝 문서 '{original_title[:30]}...' - 요약: {'✅' if document_summary else '❌'}, 메모: {'✅' if document_memo else '❌'}, 총 청크: {len(chunks)}")
        
        # 평균 점수로 정렬
        aggregated_results.sort(key=lambda x: x['average_score'], reverse=True)
        
        logger.info(f"📝 청크 집계 - 고유 문서 수: {len(aggregated_results)}")
        
        return aggregated_results

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

    def format_aggregated_results_for_rag(
        self,
        aggregated_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        집계된 검색 결과를 RAG 시스템에서 사용할 수 있는 형식으로 변환합니다.
        문서 요약과 메모 정보도 포함됩니다.

        Args:
            aggregated_results: 문서별로 집계된 검색 결과

        Returns:
            RAG 시스템용 검색 결과 리스트 (요약, 메모 포함)
        """
        formatted_results = []

        for result in aggregated_results:
            # 결합된 내용의 스니펫 생성 (요약+메모+청크 포함)
            snippet = (
                result["combined_content"][:300] + "..."
                if len(result["combined_content"]) > 300
                else result["combined_content"]
            )

            formatted_result = {
                "source_id": result["source_id"],
                "source_type": result["source_type"],
                "title": result["title"],
                "url": result["url"],
                "snippet": snippet,
                "content": result["combined_content"],        # 요약+메모+청크 내용
                "chunks_only_content": result["chunks_only_content"],  # 청크 내용만
                "summary": result["summary"],               # 문서 요약
                "memo": result["memo"],                     # 문서 메모
                "keywords": result["keywords"],
                "score": result["average_score"],
                "primary_score": result["primary_score"],
                "chunk_count": result["chunk_count"],
                "total_chunks_found": result["total_chunks_found"],
                "top_chunks": result["top_chunks"],
                "metadata": result["metadata"]
            }
            formatted_results.append(formatted_result)

        return formatted_results


# 싱글턴 인스턴스
vector_service = VectorService()
