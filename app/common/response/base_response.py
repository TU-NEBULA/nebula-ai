from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, Any

T = TypeVar("T")

class BaseResponse(Generic[T], BaseModel):
    isSuccess: bool
    code: str
    message: str
    result: Optional[T] = None

def success_response(data: Any = None, code: int = 200, message: str = "OK") -> dict:
    return {
        "code": code,
        "message": message,
        "data": data
    }

def error_response(code: int, message: str) -> dict:
    return {
        "code": code,
        "message": message,
        "data": None
    }