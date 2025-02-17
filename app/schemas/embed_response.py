from pydantic import BaseModel
from typing import List

class EmbedResponse(BaseModel):
    id: str
    s3_key: str
    embedding: List[float]
    