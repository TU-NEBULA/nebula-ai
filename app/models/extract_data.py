"""
데이터 추출 요청 모델
"""

from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Index


class ExtractDataModel(BaseModel):
    """
    데이터 추출 요청 모델
    """
    user_id: int = Field(..., alias="userId")
    url: str

    model_config = ConfigDict(populate_by_name=True)

    # SQLAlchemy Index
    __table_args__ = (
        Index("idx_extract_data_status", "status"),
        Index("idx_extract_data_user_status", "user_id", "status"),
    ) 