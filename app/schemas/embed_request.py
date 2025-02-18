from pydantic import BaseModel

class EmbedRequest(BaseModel):
    id: str
    user_id: str
    s3_key: str
    