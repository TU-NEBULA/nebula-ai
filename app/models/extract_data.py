"""
데이터 추출 요청 모델
"""

from pydantic import BaseModel, Field, ConfigDict


class ExtractDataModel(BaseModel):
    """
    데이터 추출 요청 모델
    """
    user_id: int = Field(..., alias="userId")
    url: str

    model_config = ConfigDict(populate_by_name=True)
