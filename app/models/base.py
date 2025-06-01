"""
모델 기본 클래스 모듈

이 모듈은 모든 모델에서 공통으로 사용되는 기본 클래스들을 정의합니다.

주요 기능:
- UUID 기본 모델
- 타임스탬프 기본 모델
- 모든 모델의 기본 클래스
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

class UUIDModel(SQLModel):
    """UUID 기본 모델"""
    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True)
    )

class TimestampModel(SQLModel):
    """타임스탬프 기본 모델"""
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=func.now())
    )

class BaseModel(UUIDModel, TimestampModel):
    """모든 모델의 기본 클래스"""
