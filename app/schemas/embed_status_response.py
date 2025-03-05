from pydantic import BaseModel
from typing import Optional, Any

class EmbedStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None  # result는 필요하면 타입 지정 가능
