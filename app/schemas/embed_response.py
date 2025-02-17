from pydantic import BaseModel

class EmbedResponse(BaseModel):
    id: str
    s3_key: str
    embeddings: dict
    