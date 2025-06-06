"""
직접 스트리밍 채팅 API

RabbitMQ 없이 OpenAI API를 직접 호출하여 SSE로 스트리밍합니다.
PostgreSQL에 채팅 세션과 메시지를 저장합니다.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.config import settings
from app.core.database import get_async_session
from app.schemas.chat import (
    ChatRequestModel,
    ChatSessionResponse,
    ChatMessageResponse,
    ChatSessionMessagesResponse,
    ChatSessionListResponse
)
from app.schemas.base import BaseResponse, IDResponse
from app.repositories.chat_repository import ChatRepository
from app.services.vector_service import vector_service
from app.repositories.vector_repository import VectorRepository

router = APIRouter(prefix="/chat", tags=["Chat"])

TOP_K = 10  # 검색 문서 수


async def _retrieve_context(
    user_id: int, query: str
) -> List[Tuple[str, Dict[str, Any]]]:
    """PostgreSQL 벡터 데이터베이스에서 컨텍스트 검색"""
    logger.info(f"🔍 컨텍스트 검색 시작 - user_id: {user_id}, query: {query[:50]}...")

    try:
        # 독립적인 세션으로 벡터 검색 수행
        async for db_session in get_async_session():
            # 먼저 사용자의 벡터 문서 수 확인
            total_docs = await VectorRepository.get_user_document_count(
                session=db_session,
                user_id=user_id
            )
            logger.info(f"📊 사용자 {user_id}의 총 벡터 문서 수: {total_docs}")
            
            # 전체 데이터베이스 상태 확인 (디버깅용)
            try:
                all_users_docs = await VectorRepository.get_user_document_count(
                    session=db_session,
                    user_id=None  # 전체 사용자
                )
                logger.info(f"📊 전체 데이터베이스 벡터 문서 수: {all_users_docs}")
                
                # 샘플 문서 확인
                if total_docs > 0:
                    sample_docs = await VectorRepository.get_documents_by_user(
                        session=db_session,
                        user_id=user_id,
                        limit=3
                    )
                    logger.info(f"📄 샘플 문서들:")
                    for i, doc in enumerate(sample_docs):
                        logger.info(f"  {i+1}. {doc.title[:50]} (타입: {doc.source_type})")
                        logger.info(f"     키워드: {doc.keywords}")
                        
            except Exception as e:
                logger.warning(f"⚠️ 데이터베이스 상태 확인 실패: {e}")
            
            if total_docs == 0:
                logger.warning(f"⚠️ 사용자 {user_id}의 벡터 문서가 없습니다!")
                return []
            
            # 검색 임계값을 낮춰서 더 많은 결과 포함
            low_threshold = 0.3  # 기존 0.7에서 0.3으로 낮춤
            
            # PostgreSQL 벡터 검색 수행 - user_id를 정수로 전달
            logger.info(f"🔍 벡터 검색 실행 - threshold: {low_threshold}, limit: {TOP_K}")
            search_results = await vector_service.similarity_search(
                session=db_session,
                query=query,
                user_id=user_id,  # 정수 타입 그대로 전달
                limit=TOP_K * 2,  # 더 많은 결과 요청
                similarity_threshold=low_threshold
            )
            
            logger.info(f"📊 벡터 검색 결과: {len(search_results)}개 문서 발견")
            
            # 검색 결과가 없으면 전체 사용자 대상으로 재검색
            if not search_results:
                logger.info("🔍 사용자별 검색 결과 없음, 전체 검색으로 재시도...")
                search_results = await vector_service.similarity_search(
                    session=db_session,
                    query=query,
                    user_id=None,  # 전체 사용자 대상
                    limit=TOP_K,
                    similarity_threshold=low_threshold
                )
                logger.info(f"📊 전체 검색 결과: {len(search_results)}개 문서 발견")
            
            # 벡터 검색 결과가 여전히 부족하면 하이브리드 검색 시도
            if len(search_results) < 3:
                logger.info("🔍 벡터 검색 결과 부족, 하이브리드 검색 시도...")
                try:
                    hybrid_results = await vector_service.hybrid_search(
                        session=db_session,
                        query=query,
                        user_id=user_id,  # 사용자별 하이브리드 검색
                        limit=TOP_K,
                        similarity_threshold=0.2,  # 더 낮은 임계값
                        keyword_boost=0.2
                    )
                    logger.info(f"📊 하이브리드 검색 결과: {len(hybrid_results)}개 문서 발견")
                    
                    # 기존 결과와 합치되, 중복 제거
                    existing_ids = {doc.id for doc, _ in search_results}
                    for doc, score in hybrid_results:
                        if doc.id not in existing_ids:
                            search_results.append((doc, score))
                            existing_ids.add(doc.id)
                            
                except Exception as e:
                    logger.warning(f"⚠️ 하이브리드 검색 실패: {e}")

            # 검색 결과를 기존 포맷으로 변환
            results = []
            for i, (document, score) in enumerate(search_results[:TOP_K]):
                snippet = document.content[:160].replace("\n", " ")
                metadata = {
                    "title": document.title or "(제목없음)",
                    "url": document.url or "",
                    "source_id": document.source_id,
                    "source_type": document.source_type,
                    "keywords": document.keywords or [],
                    "score": score
                }
                results.append((snippet, metadata))
                logger.debug(f"📄 문서 {i+1}: {metadata['title'][:30]} (점수: {score:.3f})")

            logger.info(f"✅ 컨텍스트 검색 완료 - 최종 결과: {len(results)}개 문서")
            return results
            
    except Exception as e:
        logger.error(f"❌ 컨텍스트 검색 중 오류: {e}")
        return []  # 검색 실패시 빈 결과 반환


def _build_messages(prompt: str, ctx_blocks: List[Tuple[str, Dict[str, Any]]]):
    # TODO: 세션 기반 대화 히스토리 추가 필요
    # - conversation_history 매개변수 추가
    # - 이전 대화 메시지들을 messages 배열에 포함
    # - 토큰 제한 고려하여 최근 N개 메시지만 포함

    if ctx_blocks:
        joined = "\n".join(
            f"{i+1}. {m.get('title','(제목없음)')} | {m.get('url','')}\n{snip}\n(유사도: {m.get('score', 0):.3f})"
            for i, (snip, m) in enumerate(ctx_blocks[:5])
        )
        ctx = f"[CONTEXT - 사용자의 북마크된 문서들]\n{joined}\n"
        logger.info(f"📝 컨텍스트 구성 완료: {len(ctx_blocks)}개 블록")
        
        system_prompt = (
            "너는 NEBULA AI 비서야. 사용자의 북마크된 문서들을 활용해 한국어로 정확하고 도움이 되는 답변을 해줘. "
            "제공된 CONTEXT 정보를 바탕으로 답변하되, 출처 문서는 번호로 표시해줘. "
            "문서의 내용을 바탕으로 구체적이고 상세한 정보를 제공해줘."
        )
    else:
        ctx = "[CONTEXT]\n(사용자의 북마크에서 관련 문서를 찾지 못했습니다)\n"
        logger.warning("⚠️ 관련 문서를 찾지 못했습니다")
        
        system_prompt = (
            "너는 NEBULA AI 비서야. 사용자의 북마크에서 관련 문서를 찾지 못했지만, "
            "일반적인 지식을 바탕으로 한국어로 도움이 되는 답변을 제공해줘. "
            "사용자가 원하는 정보에 대해 북마크에 관련 문서가 없다는 것을 알리고, "
            "대신 일반적인 정보나 추천사항을 제공해줘."
        )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": ctx},
        # TODO: 여기에 conversation_history 메시지들 추가
        # for msg in conversation_history:
        #     messages.append({"role": msg["role"], "content": msg["content"]})
        {"role": "user", "content": prompt},
    ]


async def _generate_chat_stream(  # pylint: disable=too-many-locals
    request: ChatRequestModel,
    session_id: uuid.UUID,
    user_message_id: uuid.UUID
):
    """OpenAI 스트림을 SSE 형식으로 변환하면서 PostgreSQL에 저장"""
    start_time = datetime.now(timezone.utc)
    try:
        logger.info(f"🚀 채팅 스트림 시작 - user_id: {request.user_id}, session_id: {session_id}")

        # 스트림 시작: 세션 정보 먼저 전송
        session_info = {
            "type": "session_start",
            "data": {
                "session_id": str(session_id),
                "user_message_id": str(user_message_id)
            }
        }
        yield f"data: {json.dumps(session_info, ensure_ascii=False)}\n\n"

        # API 키 확인
        if not settings.OPENAI_API_KEY:
            logger.error("❌ OpenAI API 키가 설정되지 않았습니다")
            error_msg = "OpenAI API 키가 설정되지 않았습니다"
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg}, ensure_ascii=False)}\n\n"
            return

        # TODO: 대화 히스토리 조회 추가
        # conversation_history = await _get_conversation_history(
        #     session_id=session_id,
        #     user_id=request.user_id,
        #     db_session=db_session,
        #     max_messages=10  # 최근 10개 메시지
        # )

        # RAG 검색
        try:
            ctx_blocks = await _retrieve_context(request.user_id, request.message)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"❌ 컨텍스트 검색 실패: {e}")
            ctx_blocks = []

        # LLM 설정
        logger.info("🤖 OpenAI LLM 호출 준비 중...")
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            streaming=True,
            temperature=0.7,
            timeout=30,
            max_retries=1,
            # 스트리밍 최적화를 위한 설정
            model_kwargs={
                "stream_options": {"include_usage": False},  # 사용량 정보 제외로 응답 속도 향상
            }
        )

        # 메시지 구성 (TODO: 히스토리 포함)
        messages = _build_messages(request.message, ctx_blocks)
        # TODO: messages = _build_messages(request.message, ctx_blocks, conversation_history)
        
        # 응답 스트리밍 시작
        logger.info("🚀 OpenAI 스트리밍 시작")
        yield f"data: {json.dumps({'type': 'stream_start', 'data': {'timestamp': datetime.now(timezone.utc).isoformat()}}, ensure_ascii=False)}\n\n"
        
        # 시각화 데이터 전송 (RAG 검색 결과가 있을 때)
        if ctx_blocks:
            visualization_data = _create_bookmark_visualization(ctx_blocks, request.message)
            viz_message = {
                "type": "visualization",
                "data": {
                    "graph_payload": visualization_data,
                    "context_info": {
                        "total_documents": len(ctx_blocks),
                        "search_successful": True,
                        "avg_similarity": visualization_data['statistics']['avg_similarity'],
                        "search_query": request.message,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    "filter_options": {
                        "by_source_type": visualization_data['statistics']['source_types'],
                        "by_similarity": ["high", "medium", "low"],
                        "by_keywords": list(visualization_data['statistics']['keyword_distribution'].keys())
                    },
                    "sort_options": {
                        "similarity_desc": "유사도 높은순",
                        "similarity_asc": "유사도 낮은순", 
                        "title_asc": "제목 가나다순",
                        "keywords_desc": "키워드 많은순"
                    }
                }
            }
            yield f"data: {json.dumps(viz_message, ensure_ascii=False)}\n\n"
            logger.info(f"📊 시각화 데이터 전송 완료 - 노드: {len(visualization_data['nodes'])}개, 엣지: {len(visualization_data['edges'])}개")
        else:
            # 검색 결과가 없을 때의 기본 시각화
            empty_viz = {
                "type": "visualization", 
                "data": {
                    "graph_payload": {
                        "nodes": [],
                        "edges": [],
                        "layout": "empty",
                        "message": "관련 북마크를 찾지 못했습니다"
                    },
                    "context_info": {
                        "total_documents": 0,
                        "search_successful": False,
                        "message": "검색 결과가 없습니다"
                    }
                }
            }
            yield f"data: {json.dumps(empty_viz, ensure_ascii=False)}\n\n"

        # AI 응답 수집 및 스트림
        ai_response = ""
        token_count = 0
        chunk_buffer = ""
        buffer_size = 5  # 5개 토큰마다 전송

        for chunk in llm.stream(messages):
            if chunk.content:
                token_count += 1
                ai_response += chunk.content
                chunk_buffer += chunk.content
                
                # 버퍼가 찼거나 문장 끝 표시가 있으면 전송
                should_send = (
                    len(chunk_buffer) >= buffer_size or
                    chunk.content in ['.', '!', '?', '\n', '。', '！', '？'] or
                    token_count % 3 == 0  # 3토큰마다 강제 전송
                )
                
                if should_send:
                    logger.debug(f"📝 토큰 {token_count}: 청크 전송 - {chunk_buffer[:20]}...")
                    yield f"data: {json.dumps({'type': 'chunk', 'data': chunk_buffer}, ensure_ascii=False)}\n\n"
                    chunk_buffer = ""
                    
                    # 10토큰마다 진행 상황 전송
                    if token_count % 10 == 0:
                        yield f"data: {json.dumps({'type': 'progress', 'data': {'token_count': token_count, 'status': 'generating'}}, ensure_ascii=False)}\n\n"
                    
                    # 약간의 지연으로 스트리밍 효과 보장
                    import asyncio
                    await asyncio.sleep(0.01)  # 10ms 지연
        
        # 남은 버퍼 내용 전송
        if chunk_buffer:
            logger.debug(f"📝 마지막 청크 전송: {chunk_buffer}")
            yield f"data: {json.dumps({'type': 'chunk', 'data': chunk_buffer}, ensure_ascii=False)}\n\n"
        
        # 스트리밍 완료 알림
        yield f"data: {json.dumps({'type': 'stream_complete', 'data': '응답 생성 완료'}, ensure_ascii=False)}\n\n"

        end_time = datetime.now(timezone.utc)
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)

        logger.info(f"✅ 스트림 완료 - {token_count}개 토큰 생성, 응답시간: {response_time_ms}ms")

        # AI 응답 메시지 저장 (독립적인 트랜잭션)
        try:
            ai_message = await ChatRepository.save_message(
                session=None,  # Repository에서 독립적인 세션 사용
                session_id=session_id,
                content=ai_response,
                role="assistant",
                user_id=request.user_id,
                metadata={
                    "response_time_ms": response_time_ms,
                    "token_count": token_count,
                    "model": settings.OPENAI_MODEL
                }
            )
            
            # RAG 참조 저장 (독립적인 트랜잭션)
            if ctx_blocks:
                try:
                    rag_references = []
                    for snippet, metadata in ctx_blocks:
                        rag_references.append({
                            "snippet": snippet,
                            "title": metadata.get("title", ""),
                            "url": metadata.get("url", ""),
                            "source_id": metadata.get("source_id", ""),
                            "score": float(metadata.get("score", 0.0))  # 유사도 점수
                        })

                    await ChatRepository.save_rag_references(
                        session=None,  # Repository에서 독립적인 세션 사용
                        message_id=ai_message.id,
                        references=rag_references
                    )
                except Exception as rag_error:
                    logger.error(f"❌ RAG 참조 저장 실패: {rag_error}")
                    # RAG 참조 저장 실패해도 메시지는 저장된 상태이므로 계속 진행
        
        except Exception as save_error:
            logger.error(f"❌ AI 메시지 저장 실패: {save_error}")
            # 메시지 저장 실패 시 임시 메시지 ID 생성하여 응답 완료
            ai_message = type('TempMessage', (), {'id': uuid.uuid4()})()

        # 완료 메시지 (그래프 데이터 + 메시지 ID 포함)
        graph_payload = _create_bookmark_visualization(ctx_blocks, request.message)
        completion_data = {
            "type": "session_end",
            "data": {
                "message_id": str(ai_message.id),
                 "timestamp": datetime.now(timezone.utc).isoformat(),
                "graph_payload": graph_payload,
                "session_info": {
                    "user_id": request.user_id,
                    "session_id": str(request.session_id),
                    "total_messages": 2,  # 사용자 메시지 + AI 응답
                                         "processing_time": f"{(datetime.now(timezone.utc) - start_time).total_seconds():.2f}s"
                },
                "rag_summary": {
                    "documents_found": len(ctx_blocks),
                    "search_successful": len(ctx_blocks) > 0,
                    "avg_similarity": graph_payload['statistics']['avg_similarity'] if ctx_blocks else 0
                }
            }
        }
        yield f"data: {json.dumps(completion_data, ensure_ascii=False)}\n\n"

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(f"❌ 스트림 생성 실패: {e}")
        yield f"data: {json.dumps({'type': 'error', 'data': str(e)}, ensure_ascii=False)}\n\n"


def _create_bookmark_visualization(
    ctx_blocks: List[Tuple[str, Dict[str, Any]]],
    search_query: str
) -> Dict[str, Any]:
    """
    RAG 검색 결과를 북마크 시각화용 그래프 데이터로 변환합니다.
    
    Args:
        ctx_blocks: RAG 검색 결과 [(snippet, metadata), ...]
        search_query: 검색 쿼리
        
    Returns:
        시각화용 그래프 데이터 (nodes, edges, layout 정보 포함)
    """
    if not ctx_blocks:
        return {
            "nodes": [],
            "edges": [],
            "layout": "force-3d",
            "total_bookmarks": 0,
            "search_query": "",
            "visualization_type": "bookmark_network"
        }

    # 노드 생성 (각 북마크를 노드로 표현)
    nodes = []
    for i, (snippet, metadata) in enumerate(ctx_blocks):
        # 유사도 점수에 따른 노드 크기 계산
        score = metadata.get('score', 0)
        node_size = max(10, min(30, int(score * 40)))  # 10-30 범위
        
        # 소스 타입에 따른 색상 구분
        source_type = metadata.get('source_type', 'bookmark')
        color_map = {
            'bookmark': '#4F46E5',     # 보라색
            'document': '#059669',     # 초록색  
            'article': '#DC2626',      # 빨간색
            'note': '#D97706',         # 주황색
            'webpage': '#0891B2'       # 파란색
        }
        node_color = color_map.get(source_type, '#6B7280')
        
        node = {
            "id": f"bookmark_{metadata.get('source_id', i)}",
            "label": metadata.get('title', '(제목없음)')[:30],
            "title": metadata.get('title', '(제목없음)'),
            "url": metadata.get('url', ''),
            "snippet": snippet,
            "keywords": metadata.get('keywords', []),
            "source_type": source_type,
            "similarity_score": float(score),
            "size": int(node_size),
            "color": node_color,
            "x": i * 100,  # 기본 배치
            "y": score * 100,
            "z": i * 50
        }
        nodes.append(node)

    # 엣지 생성 (북마크 간 관계 표현)
    edges = []
    
    # 1. 키워드 기반 연결
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            node_a = nodes[i]
            node_b = nodes[j]
            
            # 공통 키워드 찾기
            keywords_a = set(node_a.get('keywords', []))
            keywords_b = set(node_b.get('keywords', []))
            shared_keywords = keywords_a & keywords_b
            
            if shared_keywords:
                # 공통 키워드 수에 따른 연결 강도
                connection_weight = len(shared_keywords)
                edge_width = max(1, min(5, connection_weight))
                
                edge = {
                    "id": f"edge_{node_a['id']}_{node_b['id']}",
                    "source": node_a['id'],
                    "target": node_b['id'],
                    "weight": connection_weight,
                    "width": edge_width,
                    "color": "#94A3B8",
                    "shared_keywords": list(shared_keywords),
                    "connection_type": "keyword_similarity"
                }
                edges.append(edge)
    
    # 2. 유사도 점수 기반 연결 (고유사도 북마크들 연결)
    high_similarity_nodes = [node for node in nodes if node['similarity_score'] > 0.8]
    if len(high_similarity_nodes) > 1:
        for i in range(len(high_similarity_nodes)):
            for j in range(i + 1, len(high_similarity_nodes)):
                node_a = high_similarity_nodes[i]
                node_b = high_similarity_nodes[j]
                
                # 이미 키워드로 연결되어 있으면 건너뛰기
                existing_edge = any(
                    edge['source'] == node_a['id'] and edge['target'] == node_b['id']
                    for edge in edges
                )
                
                if not existing_edge:
                    edge = {
                        "id": f"edge_similarity_{node_a['id']}_{node_b['id']}",
                        "source": node_a['id'],
                        "target": node_b['id'],
                        "weight": 0.5,
                        "width": 2,
                        "color": "#F59E0B",
                        "connection_type": "high_similarity"
                    }
                    edges.append(edge)

    # 레이아웃 결정 (노드 수와 연결 관계에 따라)
    layout_type = _determine_layout(nodes, edges)
    
    return {
        "nodes": nodes,
        "edges": edges,
        "layout": layout_type,
        "total_bookmarks": len(nodes),
        "search_query": search_query,
        "visualization_type": "bookmark_network",
        "statistics": {
            "total_connections": int(len(edges)),
            "avg_similarity": float(sum(node['similarity_score'] for node in nodes) / len(nodes)) if nodes else 0.0,
            "source_types": list(set(node['source_type'] for node in nodes)),
            "keyword_distribution": _get_keyword_distribution(nodes),
            "similarity_range": {
                "min": float(min(node['similarity_score'] for node in nodes)) if nodes else 0.0,
                "max": float(max(node['similarity_score'] for node in nodes)) if nodes else 0.0
            }
        },
        "interaction_hints": {
            "node_hover": "북마크 상세 정보 확인",
            "node_click": "북마크 링크로 이동",
            "edge_hover": "연결 관계 확인",
            "layout_options": ["force-3d", "circular", "hierarchical", "grid"]
        }
    }


def _determine_layout(nodes: List[Dict], edges: List[Dict]) -> str:
    """노드와 엣지 수에 따라 최적의 레이아웃을 결정합니다."""
    node_count = len(nodes)
    edge_count = len(edges)
    
    if node_count <= 3:
        return "linear"
    elif node_count <= 6:
        return "circular" 
    elif edge_count > node_count * 0.7:
        return "force-3d"  # 연결이 많으면 3D 포스 레이아웃
    elif edge_count < node_count * 0.3:
        return "grid"      # 연결이 적으면 그리드 레이아웃
    else:
        return "force-2d"  # 기본 2D 포스 레이아웃


def _get_keyword_distribution(nodes: List[Dict]) -> Dict[str, int]:
    """노드들의 키워드 분포를 계산합니다."""
    keyword_count = {}
    
    for node in nodes:
        keywords = node.get('keywords', [])
        for keyword in keywords:
            keyword_count[keyword] = keyword_count.get(keyword, 0) + 1
    
    # 상위 10개 키워드만 반환
    sorted_keywords = sorted(keyword_count.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_keywords[:10])


# TODO: 대화 히스토리 조회 함수 추가 필요
# async def _get_conversation_history(
#     session_id: uuid.UUID,
#     user_id: int,
#     db_session: AsyncSession,
#     max_messages: int = 10
# ) -> List[Dict[str, str]]:
#     """
#     세션의 이전 대화 기록을 조회하여 LLM 컨텍스트에 포함할 형태로 반환
#
#     Args:
#         session_id: 채팅 세션 ID
#         user_id: 사용자 ID
#         db_session: DB 세션
#         max_messages: 최대 메시지 수 (토큰 제한 고려)
#
#     Returns:
#         [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
#
#     고려사항:
#     - 토큰 제한: GPT 모델별 최대 토큰 수 고려
#     - 성능: 자주 조회되는 히스토리는 캐싱 고려
#     - 우선순위: 최근 메시지 우선, 중요도에 따른 필터링
#     """
#     pass


@router.post(
    "/stream",
    response_class=StreamingResponse,
    summary="채팅 스트림 (PostgreSQL 연동)",
)
async def chat_stream_direct(
    request: ChatRequestModel,
    idempotency_key: Optional[str] = Header(None)
):
    """
    직접 스트리밍 방식의 채팅 API with PostgreSQL 연동
    - 채팅 세션 관리
    - 메시지 저장
    - RAG 메타데이터 저장
    - 중복 요청 방지
    """
    logger.info(f"📨 채팅 스트림 요청 수신 - user_id: {request.user_id}, idempotency_key: {idempotency_key}")

    try:
        # TODO: Idempotency key를 사용한 중복 요청 방지
        if idempotency_key:
            # Redis 또는 임시 저장소에서 중복 체크 (여기서는 간단히 로그만)
            logger.info(f"🔄 중복 방지 키 확인: {idempotency_key}")

        # 기존 세션 확인 또는 새 세션 생성
        chat_session = None
        if hasattr(request, 'session_id') and request.session_id:
            # 기존 세션 사용
            chat_session = await ChatRepository.get_session(
                session=None,  # Repository에서 독립적인 세션 사용
                session_id=uuid.UUID(request.session_id),
                user_id=request.user_id
            )

        if not chat_session:
            # 새로운 세션 생성
            chat_session = await ChatRepository.create_session(
                session=None,  # Repository에서 독립적인 세션 사용
                user_id=request.user_id,
                title=f"대화 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
            )

        # 사용자 메시지 저장
        try:
            user_message = await ChatRepository.save_message(
                session=None,  # Repository에서 독립적인 세션 사용
                session_id=chat_session.id,
                content=request.message,
                role="user",
                user_id=request.user_id
            )
            logger.info(f"💾 세션 및 사용자 메시지 저장 완료 - session_id: {chat_session.id}")
        except Exception as user_msg_error:
            logger.error(f"❌ 사용자 메시지 저장 실패: {user_msg_error}")
            # 사용자 메시지 저장 실패시 임시 ID 생성
            user_message = type('TempMessage', (), {'id': uuid.uuid4()})()

        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
            "X-Accel-Buffering": "no",  # Nginx 버퍼링 비활성화
        }

        return StreamingResponse(
            _generate_chat_stream(request, chat_session.id, user_message.id),
            media_type="text/event-stream",
            headers=headers
        )

    except Exception as e:
        logger.error(f"❌ 채팅 스트림 초기화 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"채팅 스트림 초기화 실패: {str(e)}"
        ) from e


# 🆕 세션 생성 API 추가
@router.post(
    "/sessions",
    response_model=BaseResponse[IDResponse],
    summary="새 채팅 세션 생성"
)
async def create_chat_session(
    user_id: int,
    title: Optional[str] = None
):
    """새로운 채팅 세션을 생성합니다."""
    try:
        default_title = f"새 대화 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        chat_session = await ChatRepository.create_session(
            session=None,  # Repository에서 독립적인 세션 사용
            user_id=user_id,
            title=title or default_title
        )

        return BaseResponse[IDResponse](
            success=True,
            message="채팅 세션이 성공적으로 생성되었습니다",
            data=IDResponse(id=chat_session.id)
        )

    except Exception as e:
        logger.error(f"❌ 세션 생성 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션 생성 실패: {str(e)}"
        ) from e


# 채팅 세션 관리 API 추가
@router.get(
    "/sessions",
    response_model=BaseResponse[ChatSessionListResponse],
    summary="사용자 채팅 세션 목록 조회"
)
async def get_user_sessions(
    user_id: int,
    limit: int = 20,
    offset: int = 0
):
    """사용자의 채팅 세션 목록을 조회합니다."""
    try:
        sessions = await ChatRepository.get_user_sessions(
            session=None,  # Repository에서 독립적인 세션 사용
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        session_responses = [
            ChatSessionResponse(
                id=str(session.id),
                title=session.title,
                session_type=session.session_type,
                created_at=session.created_at,
                updated_at=session.updated_at,
                is_active=session.is_active
            )
            for session in sessions
        ]

        session_list_response = ChatSessionListResponse(
            sessions=session_responses,
            total=len(sessions)
        )

        return BaseResponse[ChatSessionListResponse](
            success=True,
            message="채팅 세션 목록을 성공적으로 조회했습니다",
            data=session_list_response
        )

    except Exception as e:
        logger.error(f"❌ 세션 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션 목록 조회 실패: {str(e)}"
        ) from e


@router.get(
    "/sessions/{session_id}/messages",
    response_model=BaseResponse[ChatSessionMessagesResponse],
    summary="채팅 세션 메시지 조회"
)
async def get_session_messages(
    session_id: str,
    user_id: int
):
    """특정 채팅 세션의 메시지 목록을 조회합니다."""
    try:
        session_uuid = uuid.UUID(session_id)
        messages = await ChatRepository.get_session_messages(
            session=None,  # Repository에서 독립적인 세션 사용
            session_id=session_uuid,
            user_id=user_id
        )

        message_responses = [
            ChatMessageResponse(
                id=str(message.id),
                content=message.content,
                role=message.role,
                created_at=message.created_at,
                metadata=message.rag_metadata or {}
            )
            for message in messages
        ]

        session_messages_response = ChatSessionMessagesResponse(
            session_id=session_id,
            messages=message_responses
        )

        return BaseResponse[ChatSessionMessagesResponse](
            success=True,
            message="채팅 메시지 목록을 성공적으로 조회했습니다",
            data=session_messages_response
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="올바르지 않은 세션 ID 형식입니다"
        ) from exc
    except Exception as e:
        logger.error(f"❌ 세션 메시지 조회 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"세션 메시지 조회 실패: {str(e)}"
        ) from e
