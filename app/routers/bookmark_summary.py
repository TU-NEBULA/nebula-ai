"""
북마크 요약 API 라우터

북마크 내용을 요약하고 SSE로 스트리밍하는 API 엔드포인트를 제공합니다.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.schemas.bookmark_summary_schemas import BookmarkSummaryRequest
from app.services.bookmark_summary_service import BookmarkSummaryService

router = APIRouter(prefix="/bookmark", tags=["Bookmark Summary"])

# 서비스 인스턴스
bookmark_summary_service = BookmarkSummaryService()


@router.post(
    "/summary/stream",
    response_class=StreamingResponse,
    summary="웹페이지/S3 HTML 상세 요약 스트리밍",
    description="웹페이지 URL 또는 S3 HTML 키를 받아 AI로 상세 요약을 실시간 스트리밍합니다."
)
async def summarize_bookmark_stream(
    user_id: int = Query(..., description="사용자 ID"),
    url: Optional[str] = Query(None, description="요약할 웹페이지의 URL"),
    s3_key: Optional[str] = Query(None, description="S3에 저장된 HTML 파일의 키"),
    max_length: Optional[int] = Query(default=500, description="최대 요약 길이"),
    language: str = Query(default="ko", description="요약 언어 (ko, en)")
):
    """
    웹페이지(URL) 또는 S3 HTML 파일을 상세 요약하여 SSE로 스트리밍합니다.
    url 또는 s3_key 중 하나는 반드시 입력해야 합니다.
    
    **SSE 이벤트 타입:**
    - `progress`: 요약 진행 상황 (본문 추출, AI 요약 등)
    - `partial_summary`: 부분 요약 내용 (AI가 생성하는 실시간 텍스트)
    - `complete`: 최종 요약 결과 (메타데이터 포함)
    - `error`: 오류 발생
    - `end`: 스트림 종료
    
    **응답 데이터 구조:**
    - Progress 이벤트: `{step, progress, message, data?}`
    - Partial Summary 이벤트: `{partial_content, total_content}`
    - Complete 이벤트: `{url, s3_key, summary, total_characters, summary_length, processing_time}`
    - Error 이벤트: `{error_code, error_message, url?, s3_key?}`
    """
    logger.info(f"웹/S3 상세 요약 스트리밍 요청 - 사용자: {user_id}, url: {url}, s3_key: {s3_key}")
    try:
        if not url and not s3_key:
            raise HTTPException(
                status_code=400,
                detail="url 또는 s3_key 중 하나는 반드시 입력해야 합니다."
            )
        if language not in ["ko", "en"]:
            raise HTTPException(
                status_code=400,
                detail="language는 ko 또는 en이어야 합니다."
            )
        if max_length and (max_length < 50 or max_length > 2000):
            raise HTTPException(
                status_code=400,
                detail="max_length는 50자 이상 2000자 이하여야 합니다."
            )
        summary_request = BookmarkSummaryRequest(
            user_id=user_id,
            url=url,
            s3_key=s3_key,
            max_length=max_length,
            language=language
        )
        return StreamingResponse(
            bookmark_summary_service.generate_summary_stream(summary_request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"웹/S3 요약 API 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"웹/S3 요약 중 서버 오류가 발생했습니다: {str(e)}"
        )


@router.get(
    "/user/{user_id}/bookmarks",
    summary="사용자 북마크 목록",
    description="특정 사용자의 저장된 북마크 목록을 조회합니다."
)
async def get_user_bookmarks(
    user_id: int,
    limit: int = Query(default=20, le=100, description="조회할 북마크 수"),
    offset: int = Query(default=0, ge=0, description="시작 위치")
):
    """
    사용자의 북마크 목록을 조회합니다.
    요약 API에서 사용할 수 있는 bookmark_id들을 확인할 때 유용합니다.
    """
    try:
        from app.core.database import get_async_session
        from app.repositories.vector_repository import VectorRepository
        
        async for session in get_async_session():
            # 사용자의 북마크 문서들 조회
            documents = await VectorRepository.get_documents_by_user(
                session=session,
                user_id=user_id,
                source_type="bookmark",
                limit=limit * 3  # 중복 제거를 고려하여 더 많이 조회
            )
            
            # source_id별로 그룹화하여 중복 제거
            bookmark_map = {}
            for doc in documents:
                if doc.source_id not in bookmark_map:
                    bookmark_map[doc.source_id] = {
                        "bookmark_id": doc.source_id,
                        "title": doc.title,
                        "url": doc.url,
                        "keywords": doc.keywords,
                        "created_at": doc.created_at,
                        "chunk_count": 0
                    }
                bookmark_map[doc.source_id]["chunk_count"] += 1
            
            # 페이지네이션 적용
            bookmarks = list(bookmark_map.values())
            total_count = len(bookmarks)
            
            # offset과 limit 적용
            paginated_bookmarks = bookmarks[offset:offset + limit]
            
            return {
                "bookmarks": paginated_bookmarks,
                "total_count": total_count,
                "offset": offset,
                "limit": limit,
                "has_more": offset + limit < total_count
            }
            
    except Exception as e:
        logger.error(f"사용자 북마크 목록 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"북마크 목록 조회 중 오류가 발생했습니다: {str(e)}"
        ) 