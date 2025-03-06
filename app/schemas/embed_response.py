from pydantic import BaseModel
from typing import Optional

class EmbedResponse(BaseModel):
    id: str                      # 북마크 ID
    status: str                  # 작업 상태 (예: "queued")
    task_id: str
    message: Optional[str] = None  # 안내 메시지
