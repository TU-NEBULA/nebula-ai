"""
북마크 저장 태스크 모듈

이 모듈은 웹 페이지 북마크를 처리하고 PostgreSQL 벡터 데이터베이스에 저장하는 Celery 태스크를 정의합니다.
S3에서 HTML 콘텐츠를 가져오고, 텍스트를 추출하여 RAG에 최적화된 청크로 나눈 다음, 
사용자 키워드와 메모를 포함하여 임베딩하여 PostgreSQL pgvector에 저장합니다.
"""

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.core.config import settings
from app.core.celery_worker import celery
from app.core.database import get_async_session
from app.external.s3_service import download_html_from_s3
from app.services.vector_service import vector_service
from app.utils.text_processing import (
    extract_main_text, 
    prepare_content_for_rag,
    extract_keywords
)


def _save_bookmark_logic(user_id: str, star_id: str, s3_key: str, title: str, url: str, keywords: list, memo: str, summary: str) -> dict:
    """
    북마크를 PostgreSQL 벡터 데이터베이스에 저장하는 핵심 로직 함수

    이 함수는 S3에서 HTML 콘텐츠를 가져와 텍스트로 변환하고,
    RAG에 최적화된 방식으로 텍스트를 청크로 나눈 다음 PostgreSQL 벡터 데이터베이스에 저장합니다.
    사용자가 설정한 모든 정보(제목, URL, 키워드, 메모)를 그대로 사용합니다.
    기존에 동일한 star_id로 저장된 항목이 있으면 먼저 삭제합니다.

    Args:
        user_id (str): 사용자 ID
        star_id (str): 북마크 ID
        s3_key (str): S3에 저장된 HTML 콘텐츠의 키
        title (str): 사용자가 설정한 북마크 제목
        url (str): 원본 URL
        keywords (list): 사용자가 최종 선택한 키워드 목록
        memo (str): 사용자가 작성한 메모
        summary (str): 사용자가 확인한 요약

    Returns:
        dict: 저장 성공 여부 및 저장된 청크 수 정보
    """
    import asyncio
    
    async def _async_save_logic():
        # S3에서 HTML 다운로드 및 텍스트 추출
        html = download_html_from_s3(s3_key)
        
        # 본문 텍스트 추출 (clean text)
        body_text = extract_main_text(html)

        # 데이터베이스 세션 생성
        async for session in get_async_session():
            # 기존 북마크 관련 모든 데이터 삭제 (완전한 업데이트 보장)
            total_deleted = 0
            
            # 1. 기존 콘텐츠 청크들 삭제
            for source_type in ["bookmark", "bookmark_chunk"]:
                deleted_count = await vector_service.delete_document(
                    session=session,
                    user_id=user_id,
                    source_id=star_id,
                    source_type=source_type
                )
                total_deleted += deleted_count
            
            # 2. 특별한 형태의 source_id들도 삭제 (청크, 메모, 요약)
            # star_id로 시작하는 모든 문서 찾아서 삭제
            try:
                # star_id를 포함하는 모든 source_id 패턴 삭제
                patterns_to_delete = [
                    f"{star_id}_chunk_",  # 청크들
                    f"{star_id}_memo",    # 메모
                    f"{star_id}_summary"  # 요약
                ]
                
                for pattern in patterns_to_delete:
                    # 패턴으로 시작하는 source_id들 삭제
                    pattern_deleted = await vector_service.delete_documents_by_pattern(
                        session=session,
                        user_id=user_id,
                        source_id_pattern=pattern
                    )
                    total_deleted += pattern_deleted
                    
            except Exception as e:
                # 패턴 삭제가 지원되지 않는 경우 개별 삭제 시도
                for source_type in ["bookmark_chunk", "bookmark_memo", "bookmark_summary"]:
                    try:
                        deleted_count = await vector_service.delete_document(
                            session=session,
                            user_id=user_id,
                            source_id=f"{star_id}_memo",
                            source_type="bookmark_memo"
                        )
                        total_deleted += deleted_count
                        
                        deleted_count = await vector_service.delete_document(
                            session=session,
                            user_id=user_id,
                            source_id=f"{star_id}_summary",
                            source_type="bookmark_summary"
                        )
                        total_deleted += deleted_count
                        
                        # 청크들은 인덱스별로 삭제 (최대 20개까지 시도)
                        for i in range(20):
                            chunk_deleted = await vector_service.delete_document(
                                session=session,
                                user_id=user_id,
                                source_id=f"{star_id}_chunk_{i}",
                                source_type="bookmark_chunk"
                            )
                            total_deleted += chunk_deleted
                            if chunk_deleted == 0:  # 더 이상 삭제할 청크가 없음
                                break
                                
                    except Exception:
                        continue  # 개별 삭제 실패는 무시하고 계속
            
            # RAG에 최적화된 콘텐츠 준비
            rag_chunks = prepare_content_for_rag(
                text=body_text,
                keywords=keywords,
                memo=memo,
                summary=summary,
                chunk_size=1000,  # RAG에 최적화된 크기
                chunk_overlap=200
            )
            
            # 사용자 키워드만 사용 (추가 키워드 추출 안 함)
            # 사용자가 이미 신중하게 선택한 키워드를 그대로 존중
            
            # 각 청크를 개별적으로 저장
            saved_vectors = []
            for chunk_data in rag_chunks:
                # 청크별 메타데이터 구성
                chunk_metadata = {
                    "chunk_index": chunk_data["chunk_index"],
                    "total_chunks": chunk_data["total_chunks"],
                    "user_selected_keywords": keywords,
                    "chunk_keywords": chunk_data["chunk_keywords"],
                    "user_memo": memo,
                    "s3_key": s3_key,
                    "chunk_type": "content"
                }
                
                # 각 청크를 별도 문서로 저장
                chunk_vectors = await vector_service.save_document(
                    session=session,
                    user_id=user_id,
                    source_id=f"{star_id}_chunk_{chunk_data['chunk_index']}",
                    source_type="bookmark_chunk",
                    content=chunk_data["content"],
                    title=title,  # 사용자가 설정한 제목
                    url=url,      # 사용자가 제공한 URL
                    keywords=keywords,  # 사용자가 선택한 키워드만
                    summary=summary,
                    extra_metadata=chunk_metadata
                )
                saved_vectors.extend(chunk_vectors)
            
            # 메모가 있는 경우 별도로 저장 (RAG에서 중요도 높음)
            if memo and memo.strip():
                memo_metadata = {
                    "chunk_type": "user_memo",
                    "user_selected_keywords": keywords,
                    "s3_key": s3_key,
                    "original_content_summary": summary
                }
                
                memo_vectors = await vector_service.save_document(
                    session=session,
                    user_id=user_id,
                    source_id=f"{star_id}_memo",
                    source_type="bookmark_memo",
                    content=f"사용자 메모: {memo}\n\n관련 키워드: {', '.join(keywords)}\n\n내용 요약: {summary}",
                    title=f"[메모] {title}",  # 사용자 제목 사용
                    url=url,
                    keywords=keywords,  # 사용자 키워드만
                    summary=memo,  # 메모 자체를 요약으로 사용
                    extra_metadata=memo_metadata
                )
                saved_vectors.extend(memo_vectors)
            
            # 요약 정보도 별도로 저장 (RAG에서 개요 파악용)
            if summary and summary.strip():
                summary_metadata = {
                    "chunk_type": "summary",
                    "user_selected_keywords": keywords,
                    "s3_key": s3_key,
                    "total_content_chunks": len(rag_chunks)
                }
                
                summary_vectors = await vector_service.save_document(
                    session=session,
                    user_id=user_id,
                    source_id=f"{star_id}_summary",
                    source_type="bookmark_summary",
                    content=f"문서 요약: {summary}\n\n핵심 키워드: {', '.join(keywords)}",
                    title=f"[요약] {title}",  # 사용자 제목 사용
                    url=url,
                    keywords=keywords,  # 사용자 키워드만
                    summary=summary,
                    extra_metadata=summary_metadata
                )
                saved_vectors.extend(summary_vectors)
            
            return {
                "status": "success", 
                "inserted": len(saved_vectors),
                "deleted": total_deleted,  # 삭제된 기존 데이터 수
                "content_chunks": len(rag_chunks),
                "has_memo": bool(memo and memo.strip()),
                "has_summary": bool(summary and summary.strip()),
                "total_keywords": len(keywords),
                "user_keywords": len(keywords),  # 이제 모두 사용자 키워드
                "user_title": title,
                "user_url": url,
                "is_update": total_deleted > 0  # 기존 데이터가 있었는지 여부
            }
    
    # 비동기 함수를 동기로 실행
    return asyncio.run(_async_save_logic())


@celery.task(
    name="tasks.save_bookmark",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_jitter=True,
)
def save_bookmark_task(_self, user_id: str, star_id: str, s3_key: str, title: str, url: str, keywords: list, memo: str, summary: str) -> dict:
    """
    북마크를 PostgreSQL 벡터 데이터베이스에 저장하는 Celery 태스크

    이 태스크는 예외 발생 시 최대 3회까지 자동으로 재시도하며,
    재시도 간격은 지수적으로 증가하고 무작위 지터(jitter)가 추가됩니다.
    
    RAG 챗봇에서 효과적으로 활용할 수 있도록:
    1. 텍스트를 적절한 크기의 청크로 분할
    2. 사용자 키워드와 추출된 키워드를 결합
    3. 사용자 메모를 별도 문서로 저장 (높은 중요도)
    4. 요약 정보를 별도 문서로 저장 (개요 파악용)

    Args:
        self: Celery 태스크 인스턴스
        user_id (str): 사용자 ID
        star_id (str): 북마크 ID
        s3_key (str): S3에 저장된 HTML 콘텐츠의 키
        title (str): 사용자가 설정한 북마크 제목
        url (str): 원본 URL
        keywords (list): 사용자가 최종 선택한 키워드 목록
        memo (str): 사용자가 작성한 메모
        summary (str): 사용자가 확인한 요약

    Returns:
        dict: 저장 성공 여부 및 상세 정보
    """
    return _save_bookmark_logic(user_id, star_id, s3_key, title, url, keywords, memo, summary)
