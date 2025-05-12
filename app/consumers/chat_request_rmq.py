import os
import json
import uuid
import logging
import asyncio
import traceback
from aio_pika import IncomingMessage, Message
from pydantic import BaseModel, Field
from typing import Any, Dict, List
from openai import AsyncOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain.prompts.chat import (
    ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate,
)
from app.core.config import settings
from app.core.rabbit import get_rabbit_connection

# 로깅 설정 (stdout에 즉시 출력)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
log = logging.getLogger(__name__)
# httpx 디버그 로깅
logging.getLogger("httpx").setLevel(logging.DEBUG)

# LangSmith 트레이싱 활성화
os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGSMITH_API_KEY)

# 임베딩 및 OpenAI 비동기 클라이언트
embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBED_MODEL)
async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 파라미터
TOP_K = 10
ANSWER_N = 5

class ChatRequestModel(BaseModel):
    user_id: int = Field(..., alias="userId")
    message: str

    class Config:
        allow_population_by_field_name = True

async def on_chat_message(ch, message: IncomingMessage):
    """
    메시지 처리: 벡터 검색 후 AsyncOpenAI 스트리밍, 로그 추가
    """
    async with message.process():
        try:
            log.debug("Received message body: %s", message.body)
            req = ChatRequestModel.model_validate_json(message.body)
            log.info("[ChatReq] user_id=%s, message=%s", req.user_id, req.message)

            # 1) VectorStore 생성 및 검색
            try:
                log.debug("Building Chroma vectorstore...")
                vectorstore = Chroma(
                    persist_directory=settings.CHROMA_DB_URI,
                    embedding_function=embeddings,
                    collection_name="nebula_html",
                )
                log.info("Querying vectorstore for top %d docs...", TOP_K)
                docs_scores = vectorstore.similarity_search_with_score(req.message, k=TOP_K)
            except Exception as e:
                log.error("Chroma vectorstore init/search failed: %s", e)
                docs_scores = []

            # 필터링
            filtered = [(d, s) for d, s in docs_scores if d.metadata.get("user_id") == req.user_id]
            log.info("Filtered %d docs for user", len(filtered))

            # 2) 결과 없을 때 종료
            if not filtered:
                log.warning("No documents found for query, sending fallback")
                fallback = {"type": "end", "data": {"answer": "관련 자료가 없어요.", "graphPayload": {}}}
                await ch.default_exchange.publish(
                    Message(
                        body=json.dumps(fallback).encode(),
                        correlation_id=message.correlation_id or str(uuid.uuid4())
                    ),
                    routing_key=message.reply_to
                )
                return

            # 3) 컨텍스트 및 그래프 데이터 준비
            context_lines, nodes, edges = [], [], []
            for idx, (doc, _) in enumerate(filtered[:ANSWER_N]):
                md = doc.metadata
                snippet = getattr(doc, 'snippet', doc.page_content[:200])
                line = f"{idx+1}. {md.get('title')} | {md.get('url')} | {snippet}"
                context_lines.append(line)
                nodes.append({
                    "id": md.get("id"),
                    "label": md.get("title"),
                    "url": md.get("url"),
                    "tags": md.get("tags", [])
                })
            for i in range(len(nodes)):
                for j in range(i+1, len(nodes)):
                    shared = set(nodes[i]["tags"]) & set(nodes[j]["tags"])
                    if shared:
                        edges.append({
                            "source": nodes[i]["id"],
                            "target": nodes[j]["id"],
                            "weight": len(shared)
                        })
            graph_payload = {"nodes": nodes, "edges": edges, "layout": "force-3d"}
            log.debug("Prepared graph payload: %d nodes, %d edges", len(nodes), len(edges))

            # 4) OpenAI 스트리밍 호출
            system_tmpl = (
                "너는 NEBULA 챗봇입니다. 상위 5개 북마크를 제목·URL·요약 형태로 간결히 응답하세요."
            )
            human_tmpl = (
                "[CONTEXT]\n" + "\n".join(context_lines) + "\n\n[USER]\n{query}"
            )
            prompt_msgs = ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(system_tmpl),
                HumanMessagePromptTemplate.from_template(human_tmpl)
            ]).format_prompt(query=req.message).to_messages()
            log.info("Sending streaming request to OpenAI with %d messages", len(prompt_msgs))

            # 5) 스트림 전송
            async for chunk in async_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=prompt_msgs,
                stream=True
            ):
                delta = chunk.choices[0].delta.content or ""
                log.debug("Stream chunk: %s", delta)
                await ch.default_exchange.publish(
                    Message(
                        body=json.dumps({"type": "chunk", "data": delta}).encode(),
                        correlation_id=message.correlation_id
                    ),
                    routing_key=message.reply_to
                )

            # 6) 완료 이벤트 전송
            log.info("Streaming complete, sending graph payload")
            await ch.default_exchange.publish(
                Message(
                    body=json.dumps({"type": "end", "data": graph_payload}).encode(),
                    correlation_id=message.correlation_id
                ),
                routing_key=message.reply_to
            )
            log.info("[ChatDone] user_id=%s", req.user_id)

        except Exception:
            tb = traceback.format_exc()
            log.error("Chat 처리 오류: %s", tb)
            if message.reply_to:
                err = {"type": "end", "error": tb}
                await ch.default_exchange.publish(
                    Message(
                        body=json.dumps(err).encode(),
                        correlation_id=message.correlation_id or str(uuid.uuid4())
                    ),
                    routing_key=message.reply_to
                )

async def start_chat_consumer():
    conn = await get_rabbit_connection()
    ch = await conn.channel()
    await ch.set_qos(prefetch_count=1)
    q = await ch.declare_queue(settings.CHAT_REQ_QUEUE, durable=True)
    await q.consume(lambda msg: on_chat_message(ch, msg))
    log.info("Chat consumer listening on queue %s", settings.CHAT_REQ_QUEUE)
