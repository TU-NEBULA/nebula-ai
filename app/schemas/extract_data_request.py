from pydantic import BaseModel

class ExtractDataRequest(BaseModel):
    id: int
    user_id: str
    s3_key: str
    