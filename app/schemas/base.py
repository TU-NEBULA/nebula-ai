"""
기본 스키마 모듈

이 모듈은 모든 API 응답 스키마를 정의합니다.

주요 기능:
- 기본 API 응답 스키마
- 에러 응답 스키마
"""
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field
from uuid import UUID

DataT = TypeVar("DataT")

class BaseResponse(BaseModel, Generic[DataT]):
    """기본 API 응답 스키마"""
    success: bool = Field(default=True, description="요청 성공 여부")
    message: str = Field(default="Success", description="응답 메시지")
    data: Optional[DataT] = Field(default=None, description="응답 데이터")

class ErrorResponse(BaseModel):
    """에러 응답 스키마"""
    success: bool = Field(default=False)
    message: str = Field(description="에러 메시지")
    error_code: Optional[str] = Field(default=None, description="에러 코드")
    details: Optional[Any] = Field(default=None, description="에러 상세 정보")

class PaginationMeta(BaseModel):
    """페이지네이션 메타데이터"""
    page: int = Field(ge=1, description="현재 페이지")
    size: int = Field(ge=1, le=100, description="페이지 크기")
    total: int = Field(ge=0, description="전체 항목 수")
    total_pages: int = Field(ge=0, description="전체 페이지 수")

class PaginatedResponse(BaseModel, Generic[DataT]):
    """페이지네이션 응답 스키마"""
    success: bool = Field(default=True)
    message: str = Field(default="Success")
    data: List[DataT] = Field(description="데이터 목록")
    meta: PaginationMeta = Field(description="페이지네이션 정보")

class IDResponse(BaseModel):
    """ID만 반환하는 응답 스키마"""
    id: UUID = Field(description="생성/수정된 리소스 ID")
