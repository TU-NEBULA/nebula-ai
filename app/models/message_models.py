"""
메시지 전용 모델들

RabbitMQ 메시지 전송에 사용되는 Pydantic 모델들입니다.
SQLModel과 분리하여 충돌을 방지합니다.
"""
from datetime import datetime
from typing import List, Dict
from pydantic import BaseModel, Field

class BookmarkRelationshipMessage(BaseModel):
    """
    북마크 관계 저장 메시지 모델
    
    RabbitMQ를 통해 Spring Boot로 전송되는 북마크 관계 데이터입니다.
    """
    user_id: int
    source_bookmark: Dict = Field(..., description="소스 북마크 정보")
    similar_bookmarks: List[Dict] = Field(..., description="유사한 북마크들과 유사도")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class BookmarkNodeData(BaseModel):
    """북마크 노드 데이터"""
    bookmark_id: str
    title: str
    url: str
    keywords: List[str]
    summary: str

class SimilarBookmarkData(BaseModel):
    """유사한 북마크 데이터"""
    bookmark_id: str
    similarity_score: float
    title: str
    url: str 