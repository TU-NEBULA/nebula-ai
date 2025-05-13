"""
사용자 채팅 요청 처리 모듈

이 모듈은 사용자의 채팅 요청을 처리하고, 벡터 데이터베이스에서 관련 문서를 검색하여
사용자의 질문에 대한 응답을 생성합니다. 또한 시각화를 위한 그래프 데이터도 함께 반환합니다.
"""
import asyncio
from typing import List, Dict

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain.prompts.chat import (
    ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate,
)

from app.core.config import settings

# 검색할 최대 문서 수
TOP_K=10
# 응답에 포함할 문서 수
ANSWER_N=5

# OpenAI 임베딩 모델 초기화
embeddings = OpenAIEmbeddings(
    model=settings.OPENAI_EMBED_MODEL or "text-embedding-3-small"
)

async def process_chat_request(user_id: int, message: str,) -> Dict[str, List[Dict]]:
    """
    사용자의 채팅 요청을 처리하고 관련 문서와 응답을 생성합니다.
    
    사용자 ID와 메시지를 받아 다음과 같은 작업을 수행합니다:
    1. 벡터 데이터베이스에서 사용자의 북마크 중 메시지와 관련된 문서를 검색합니다.
    2. 검색된 문서를 사용하여 LLM으로 응답을 생성합니다.
    3. 문서들의 관계를 시각화하기 위한 그래프 데이터를 구성합니다.
    
    Args:
        user_id (int): 사용자 ID
        message (str): 사용자의 메시지/질문
        
    Returns:
        Dict[str, List[Dict]]: 응답 텍스트와 그래프 데이터를 포함한 딕셔너리
    """

    vectorstore = Chroma(
        persist_directory=settings.CHROMA_DB_URI,
        embedding_function=embeddings,
        collection_name="nebula_html",
    )

    docs_and_scores = vectorstore.similarity_search_with_score(message, k=TOP_K)
    filtered = []
    for doc, score in docs_and_scores:
        md = doc.metadata
        if md.get("user_id") != user_id:
            continue
        filtered.append((doc, score))
        if len(filtered) >= TOP_K:
            break

    if not filtered:
        return {
            "answer": "관련 자료가 없어요. 다른 키워드로 시도해 볼까요?",
            "graphPayload": {"nodes": [], "edges": [], "layout": "force-3d"},
        }

    context_lines = []
    nodes, edges = [], []
    for idx, (doc, score) in enumerate(filtered):
        md = doc.metadata
        title = md.get("title", "Untitled")
        url = md.get("url", "")
        keywords = md.get("keywords", [])
        snippet = doc.snippet
        context_lines.append(
            f"{idx+1}. 제목: {title} | URL: {url} | 요약: {snippet}"
        )
        nodes.append({
            "id": md.get("id", f"doc_{idx}"),
            "label": title,
            "url": url,
            "keywords": keywords,
        })

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

    system_template = (
        "너는 NEBULA 챗봇입니다. 검색 결과를 바탕으로 사용자에게 상위 5개 북마크를 “제목·URL·요약” 형태로 "
        "간결히 응답하고, 응답 끝에 항상 GRAPH_PAYLOAD(JSON)도 포함해 주세요."
    )
    human_template = (
        "[CONTEXT]\n" + "\n".join(context_lines[:ANSWER_N]) + "\n\n[USER]\n{query}"
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

    response_text = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: llm(chat_prompt.format_prompt(query=message).to_messages()).content,
    )

    return {
        "answer": response_text,
        "graphPayload": graph_payload,
    }
