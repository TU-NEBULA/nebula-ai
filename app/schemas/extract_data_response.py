from pydantic import BaseModel

class ExtractDataResponse(BaseModel):
    id: str
    image_url: str
    keywords: list
    