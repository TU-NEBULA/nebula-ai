import json
# import openai

from typing import List, Dict
from app.core.config import settings
from app.core.chroma_db import ChromaDBClient
from sqlalchemy import select

async def process_chat_request(
    user_id: int,
    message: str,
    scope: str = "both"
) -> Dict[str, List[Dict]]:
    """
    1) 사용자 메시지 임베딩
    2) scope(visit/bookmark/both) 기반 메타 필터 설정
    3) 벡터 DB(Chroma)에서 유사 문서 검색
    4) 실제 DB에서 Bookmark/Visit 기록 로드
    5) RAG 프롬프트 구성 → OpenAI 호출
    6) JSON 파싱 후 결과 반환
    """
    
    return f"user_id:{user_id}\nmessage: {message}\n응 통과야"
