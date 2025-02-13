from pydantic import BaseModel
from typing import List

class DocumentCreate(BaseModel):
    doc_id: str
    text: str
    embedding: List[float]

class DocumentSearch(BaseModel):
    query_embedding: List[float]
    top_k: int = 5
