from pydantic import BaseModel

class EmbedResponse(BaseModel):
    id: str
    simmilar_ids: list[str]
    