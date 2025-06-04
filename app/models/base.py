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
from sqlmodel import Field as SQLField, SQLModel
from sqlalchemy import Column, DateTime, text


class BaseModel(SQLModel):
    """모든 모델의 기본 클래스"""
    # UUID 기본 키 - sa_column과 primary_key를 분리
    id: UUID = SQLField(
        default_factory=uuid4,
        primary_key=True
    )

    # 타임스탬프 필드
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=text('NOW()'))
    )
    updated_at: Optional[datetime] = SQLField(
        default=None,
        sa_column=Column(DateTime(timezone=True), onupdate=text('NOW()'))
    )


# 하위 호환성을 위한 별칭들
Base = SQLModel
TimestampModel = SQLModel  # 믹스인으로 사용하지 말고 각 모델에서 개별 정의
