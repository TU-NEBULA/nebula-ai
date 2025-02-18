from pydantic import BaseModel

class ExtractDataRequest(BaseModel):
    id: str
    user_id: str
    s3_key: str
    