from pydantic import BaseModel, Field

class ChatPrompt(BaseModel):
    prompt: str
    user_id: int | None = None


class ChatRequestModel(BaseModel):
    """
    RabbitMQ로 들어오는 프롬프트 메시지 검증용.
    { "userId": 42, "message": "안녕?" }
    또는
    { "user_id": 42, "message": "안녕?" }
    """
    user_id: int = Field(..., alias="userId")

    message: str

    class Config:
        allow_population_by_field_name = True
        populate_by_name = True
        