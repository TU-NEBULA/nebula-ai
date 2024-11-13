from pydantic import BaseModel, HttpUrl

class UrlInput(BaseModel):
    url: HttpUrl