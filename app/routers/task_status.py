from fastapi import APIRouter
from celery.result import AsyncResult

router = APIRouter()

@router.get("/task/status/{task_id}")
def check_task_status(task_id: str):
    """
    Celery 태스크 상태 조회
    """
    result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "state": result.state,  # PENDING, STARTED, SUCCESS, FAILURE
        "result": result.result  # 성공 시 결과 값
    }
