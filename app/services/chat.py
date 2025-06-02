"""
사용자 채팅 요청 처리 모듈

이 모듈은 사용자의 채팅 요청을 처리하고, PostgreSQL 벡터 데이터베이스에서 관련 문서를 검색하여
사용자의 질문에 대한 응답을 생성합니다. 또한 시각화를 위한 그래프 데이터도 함께 반환합니다.
"""
import asyncio
from typing import List, Dict

from langchain_openai import ChatOpenAI
from langchain.prompts.chat import (
    ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_session
from app.services.vector_service import vector_service

# 검색할 최대 문서 수
TOP_K = 10
# 응답에 포함할 문서 수
ANSWER_N = 5

async def process_chat_request(user_id: str, message: str, session: AsyncSession = None) -> Dict[str, List[Dict]]:
    """
    사용자의 채팅 요청을 처리하고 관련 문서와 응답을 생성합니다.
    
    사용자 ID와 메시지를 받아 다음과 같은 작업을 수행합니다:
    1. PostgreSQL 벡터 데이터베이스에서 사용자의 북마크 중 메시지와 관련된 문서를 검색합니다.
    2. 검색된 문서를 사용하여 LLM으로 응답을 생성합니다.
    3. 문서들의 관계를 시각화하기 위한 그래프 데이터를 구성합니다.
    
    Args:
        user_id (str): 사용자 ID
        message (str): 사용자의 메시지/질문
        session (AsyncSession): 데이터베이스 세션 (옵션)
        
    Returns:
        Dict[str, List[Dict]]: 응답 텍스트와 그래프 데이터를 포함한 딕셔너리
    """
    # 세션이 제공되지 않은 경우 새로 생성
    if session is None:
        async for db_session in get_async_session():
            return await process_chat_request(user_id, message, db_session)

    # PostgreSQL 벡터 검색 수행
    search_results = await vector_service.similarity_search(
        session=session,
        query=message,
        user_id=user_id,
        limit=TOP_K,
        similarity_threshold=0.7
    )

    if not search_results:
        return {
            "answer": "관련 자료가 없어요. 다른 키워드로 시도해 볼까요?",
            "graphPayload": {"nodes": [], "edges": [], "layout": "force-3d"},
        }

    # 검색 결과를 RAG 형식으로 변환
    formatted_results = vector_service.format_search_results_for_rag(search_results)

    context_lines = []
    nodes, edges = [], []
    
    for idx, result in enumerate(formatted_results[:ANSWER_N]):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        keywords = result.get("keywords", [])
        snippet = result.get("snippet", "")
        
        context_lines.append(
            f"{idx+1}. 제목: {title} | URL: {url} | 요약: {snippet}"
        )
        nodes.append({
            "id": result.get("source_id", f"doc_{idx}"),
            "label": title,
            "url": url,
            "keywords": keywords,
        })

    # 노드 간의 연결 생성 (키워드 기반)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            shared = set(nodes[i]["keywords"]) & set(nodes[j]["keywords"])
            if shared:
                edges.append({
                    "source": nodes[i]["id"],
                    "target": nodes[j]["id"],
                    "weight": len(shared),
                })

    graph_payload = {"nodes": nodes, "edges": edges, "layout": "force-3d"}

    # ChatGPT 프롬프트 구성
    system_template = (
        "너는 NEBULA 챗봇입니다. 검색 결과를 바탕으로 사용자에게 상위 5개 북마크를 '제목·URL·요약' 형태로 "
        "간결히 응답하고, 응답 끝에 항상 GRAPH_PAYLOAD(JSON)도 포함해 주세요."
    )
    human_template = (
        "[CONTEXT]\n" + "\n".join(context_lines) + "\n\n[USER]\n{query}"
    )

    chat_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_template),
        HumanMessagePromptTemplate.from_template(human_template),
    ])

    llm = ChatOpenAI(
        model_name=settings.OPENAI_MODEL,
        temperature=0.2,
        request_timeout=60,
    )

    # 비동기로 LLM 호출
    response_text = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: llm(chat_prompt.format_prompt(query=message).to_messages()).content,
    )

    return {
        "answer": response_text,
        "graphPayload": graph_payload,
    }
