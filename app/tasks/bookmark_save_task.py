"""
북마크 저장 태스크 모듈

이 모듈은 웹 페이지 북마크를 처리하고 PostgreSQL 벡터 데이터베이스에 저장하는 Celery 태스크를 정의합니다.
S3에서 HTML 콘텐츠를 가져오고, 텍스트를 추출하여 청크로 나눈 다음, 임베딩하여 PostgreSQL pgvector에 저장합니다.
"""

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.celery_worker import celery
from app.core.database import get_async_session
from app.external.s3_service import download_html_from_s3
from app.services.vector_service import vector_service


def _save_bookmark_logic(user_id: str, star_id: str, s3_key: str, keywords: list, memo: str, summary: str) -> dict:
    """
    북마크를 PostgreSQL 벡터 데이터베이스에 저장하는 핵심 로직 함수

    이 함수는 S3에서 HTML 콘텐츠를 가져와 텍스트로 변환하고,
    텍스트를 청크로 나눈 다음 PostgreSQL 벡터 데이터베이스에 저장합니다.
    기존에 동일한 star_id로 저장된 항목이 있으면 먼저 삭제합니다.

    Args:
        user_id (str): 사용자 ID
        star_id (str): 북마크 ID
        s3_key (str): S3에 저장된 HTML 콘텐츠의 키
        keywords (list): 북마크와 관련된 키워드 목록
        memo (str): 사용자가 작성한 메모
        summary (str): 북마크 내용 요약

    Returns:
        dict: 저장 성공 여부 및 저장된 청크 수 정보
    """
    import asyncio
    
    async def _async_save_logic():
        # S3에서 HTML 다운로드 및 텍스트 추출
        html = download_html_from_s3(s3_key)
        soup = BeautifulSoup(html, "html.parser")
        body_text = soup.get_text(separator="\n")

        # 데이터베이스 세션 생성
        async for session in get_async_session():
            # 기존 북마크 데이터 삭제
            deleted_count = await vector_service.delete_document(
                session=session,
                user_id=user_id,
                source_id=star_id,
                source_type="bookmark"
            )
            
            # 새로운 북마크 데이터 저장
            saved_vectors = await vector_service.save_document(
                session=session,
                user_id=user_id,
                source_id=star_id,
                source_type="bookmark",
                content=body_text,
                title=None,  # 필요한 경우 별도로 추출
                url=None,    # 필요한 경우 별도로 제공
                keywords=keywords,
                summary=summary,
                extra_metadata={
                    "s3_key": s3_key,
                    "memo": memo
                }
            )
            
            return {"status": "success", "inserted": len(saved_vectors)}
    
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
def save_bookmark_task(_self, user_id: str, star_id: str, s3_key: str, keywords: list, memo: str, summary: str) -> dict:
    """
    북마크를 PostgreSQL 벡터 데이터베이스에 저장하는 Celery 태스크

    이 태스크는 예외 발생 시 최대 3회까지 자동으로 재시도하며,
    재시도 간격은 지수적으로 증가하고 무작위 지터(jitter)가 추가됩니다.

    Args:
        self: Celery 태스크 인스턴스
        user_id (str): 사용자 ID
        star_id (str): 북마크 ID
        s3_key (str): S3에 저장된 HTML 콘텐츠의 키
        keywords (list): 북마크와 관련된 키워드 목록
        memo (str): 사용자가 작성한 메모
        summary (str): 북마크 내용 요약

    Returns:
        dict: 저장 성공 여부 및 저장된 청크 수 정보
    """
    return _save_bookmark_logic(user_id, star_id, s3_key, keywords, memo, summary)
