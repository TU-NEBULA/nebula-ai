"""
채팅 요청 메시지 소비자 모듈

이 모듈은 RabbitMQ를 통해 사용자의 채팅 요청을 받아 처리합니다.
벡터 데이터베이스에서 관련 데이터를 찾아 OpenAI API를 통한 비동기 스트리밍 응답을 제공합니다.
시각화를 위한 그래프 데이터도 함께 생성합니다.
"""
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
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True  # 기존 로거 설정을 덮어쓰기
)
log = logging.getLogger(__name__)
# httpx 디버그 로깅 활성화
logging.getLogger("httpx").setLevel(logging.DEBUG)

# LangSmith 트레이싱 활성화 (랭체인 모니터링을 위한 설정)
os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGSMITH_API_KEY)

# 임베딩 및 OpenAI 비동기 클라이언트 초기화
embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBED_MODEL)
async_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 검색 및 응답 관련 파라미터
TOP_K = 10  # 검색할 최대 문서 수
ANSWER_N = 5  # 응답에 포함할 문서 수

class ChatRequestModel(BaseModel):
    """
    채팅 요청 모델
    
    RabbitMQ를 통해 수신된 채팅 요청을 검증하고 파싱하기 위한 모델입니다.
    
    Attributes:
        user_id (int): 사용자 ID
        message (str): 사용자의 채팅 메시지/질문
    """
    user_id: int = Field(..., alias="userId")
    message: str

    class Config:
        allow_population_by_field_name = True

async def on_chat_message(ch, message: IncomingMessage):
    """
    채팅 메시지 처리 핸들러
    
    RabbitMQ에서 받은 채팅 요청 메시지를 처리합니다. 다음 단계로 수행됩니다:
    1. 사용자 요청 검증 및 파싱
    2. 벡터 데이터베이스에서 관련 문서 검색
    3. 그래프 데이터 생성
    4. OpenAI API를 사용한 비동기 스트리밍 응답 생성
    5. 응답 및 그래프 데이터 전송
    
    Args:
        ch: RabbitMQ 채널 객체
        message (IncomingMessage): RabbitMQ에서 받은 메시지 객체
    """
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
            # 메시지 처리 완료 표시
            await message.ack()
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

        # 5) 스트림 전송 - 타임아웃 설정 추가
        try:
            completion = await asyncio.wait_for(
                async_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[{"role": msg.type, "content": msg.content} for msg in prompt_msgs],
                    stream=True
                ),
                timeout=60  # 60초 타임아웃 설정
            )
            
            # 스트림 처리
            async for chunk in completion:
                delta = chunk.choices[0].delta.content
                if delta is not None:  # None 체크 추가
                    log.debug("Stream chunk: %s", delta)
                    await ch.default_exchange.publish(
                        Message(
                            body=json.dumps({"type": "chunk", "data": delta}).encode(),
                            correlation_id=message.correlation_id
                        ),
                        routing_key=message.reply_to
                    )
                await asyncio.sleep(0)  # 이벤트 루프에게 제어권 양보
                
        except asyncio.TimeoutError:
            log.error("OpenAI streaming timed out after 60 seconds")
            await ch.default_exchange.publish(
                Message(
                    body=json.dumps({"type": "end", "data": {"answer": "응답 시간이 초과되었습니다.", "graphPayload": graph_payload}}).encode(),
                    correlation_id=message.correlation_id
                ),
                routing_key=message.reply_to
            )
            await message.ack()
            return

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
        
        # 메시지 처리 완료 표시
        await message.ack()

    except Exception as e:
        tb = traceback.format_exc()
        log.error("Chat 처리 오류: %s", tb)
        if message and hasattr(message, 'reply_to') and message.reply_to:
            err = {"type": "end", "error": str(e), "detail": tb}
            try:
                await ch.default_exchange.publish(
                    Message(
                        body=json.dumps(err).encode(),
                        correlation_id=message.correlation_id or str(uuid.uuid4())
                    ),
                    routing_key=message.reply_to
                )
            except Exception as pub_err:
                log.error("에러 메시지 발행 실패: %s", pub_err)
        
        # 에러 발생해도 메시지 처리 완료로 표시
        try:
            await message.ack()
        except Exception as ack_err:
            log.error("Message ack 실패: %s", ack_err)

async def start_chat_consumer():
    """
    채팅 콘슈머 시작 함수
    
    RabbitMQ에 연결하고 채팅 요청 큐를 선언한 후 메시지 소비를 시작합니다.
    연결에 실패할 경우 지수 백오프를 사용한 재연결 로직을 적용합니다.
    
    최대 5회까지 재연결을 시도하고, 성공하면 새로운 콘슈머를 시작합니다.
    """
    retry_count = 0
    max_retries = 5
    
    while retry_count < max_retries:
        try:
            log.info("RabbitMQ 연결 시도 중...")
            conn = await get_rabbit_connection()
            ch = await conn.channel()
            await ch.set_qos(prefetch_count=1)
            q = await ch.declare_queue(settings.CHAT_REQ_QUEUE, durable=True)
            
            # 연결 성공 로깅
            log.info("Chat consumer listening on queue %s", settings.CHAT_REQ_QUEUE)
            
            # 메시지 소비 시작
            await q.consume(on_chat_message)
            
            # 연결 유지 (이벤트 루프에서 대기)
            while True:
                await asyncio.sleep(3600)  # 1시간마다 확인
                
        except Exception as e:
            retry_count += 1
            log.error("RabbitMQ 연결 실패 (%d/%d): %s", retry_count, max_retries, e)
            
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # 지수 백오프
                log.info("재연결 대기 중... %d초", wait_time)
                await asyncio.sleep(wait_time)
            else:
                log.critical("최대 재시도 횟수 초과. 채팅 컨슈머 시작 실패.")
                raise