from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StarCreate(BaseModel):
    id: str
    title: str
    site_url: str
    thumnail_url: Optional[str] = None
    summary_AI: Optional[str] = None
    memo_member: Optional[str] = None
    views: int = 0
    html_file_url: Optional[str] = None
    embedding: Optional[list[float]] = None 
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

