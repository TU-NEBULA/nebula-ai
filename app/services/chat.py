import json
import asyncio
from typing import List, Dict

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.vectorstores import Chroma
from langchain.prompts.chat import (
    ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate,
)

from app.core.config import settings
from app.core.chroma_db import ChromaDBClient

TOP_K = 10 
ANSWER_N = 5 

embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBED_MODEL or "text-embedding-3-small")


async def process_chat_request(
    user_id: int,
    message: str,
) -> Dict[str, List[Dict]]:
    chroma_client = ChromaDBClient()
    collection = chroma_client.get_or_create_collection(embedding_function=embeddings)
    vectorstore = Chroma(
        collection_name=collection.name,
        client=chroma_client.client,
        embedding_function=embeddings,
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
            shared = set(nodes[i]["tags"]) & set(nodes[j]["tags"])
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