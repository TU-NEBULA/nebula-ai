from fastapi import APIRouter
from app.tasks.keyword_sync_task import sync_user_keywords

router = APIRouter()

@router.post("/keyword-sync")
def keyword_sync(user_id: str):
    """
    Neo4J에서 사용자의 상위 키워드를 조회하여 ChromaDB에 저장
    """
    task = sync_user_keywords.delay(user_id)
    return {"status": "started", "task_id": task.id}
