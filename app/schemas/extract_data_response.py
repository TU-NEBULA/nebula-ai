from pydantic import BaseModel

class ExtractDataResponse(BaseModel):
    id: int
    image_url: str
    keywords: list
    