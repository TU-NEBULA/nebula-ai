from pydantic import BaseModel, HttpUrl

class DataInputs(BaseModel):
    url: HttpUrl
    html_content: str = None
