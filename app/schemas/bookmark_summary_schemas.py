"""
북마크 요약 스키마

북마크 요약 API를 위한 요청/응답 스키마들을 정의합니다.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator
from uuid import UUID

class BookmarkSummaryRequest(BaseModel):
    """북마크 요약 요청 스키마"""
    user_id: int = Field(..., description="사용자 ID")
    url: str | None = Field(None, description="요약할 웹페이지의 URL")
    s3_key: str | None = Field(None, description="요약할 S3 HTML 파일의 키")
    max_length: Optional[int] = Field(default=500, description="최대 요약 길이")
    language: str = Field(default="ko", description="요약 언어 (ko, en)")

    @model_validator(mode="after")
    def check_url_or_s3_key(self):
        if not self.url and not self.s3_key:
            raise ValueError("url 또는 s3_key 중 하나는 반드시 입력해야 합니다.")
        return self

class BookmarkSummaryProgress(BaseModel):
    """북마크 요약 진행 상황"""
    step: str = Field(..., description="현재 단계")
    progress: int = Field(..., description="진행률 (0-100)")
    message: str = Field(..., description="상태 메시지")
    data: Optional[Dict[str, Any]] = Field(default=None, description="추가 데이터")

class BookmarkSummaryResult(BaseModel):
    """북마크 요약 결과"""
    url: Optional[str] = Field(default=None, description="요약 대상 URL")
    s3_key: Optional[str] = Field(default=None, description="요약 대상 S3 키")
    summary: str = Field(..., description="요약 내용")
    total_characters: int = Field(..., description="원문 총 문자 수")
    summary_length: int = Field(..., description="요약 문자 수")
    processing_time: float = Field(..., description="처리 시간(초)")

class BookmarkSummaryError(BaseModel):
    """북마크 요약 오류"""
    error_code: str = Field(..., description="오류 코드")
    error_message: str = Field(..., description="오류 메시지")
    url: Optional[str] = Field(default=None, description="요약 대상 URL")
    s3_key: Optional[str] = Field(default=None, description="요약 대상 S3 키")

# SSE 이벤트 타입들
class SSEEventType:
    """SSE 이벤트 타입 상수"""
    PROGRESS = "progress"
    PARTIAL_SUMMARY = "partial_summary"
    COMPLETE = "complete" 
    ERROR = "error"
    END = "end" 