from pydantic import BaseModel

class EmbedRequest(BaseModel):
    id: str
    s3_key: str
    