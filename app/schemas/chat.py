"""
채팅 스키마 모듈

이 모듈은 채팅 관련 스키마들을 정의합니다.

주요 기능:
- 채팅 프롬프트 요청 스키마
- 채팅 메시지 요청 스키마
- 채팅 스트리밍 요청 스키마
- RAG 검색 결과 스키마
- 피드백 요청 스키마
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class ChatPrompt(BaseModel):
    """채팅 프롬프트 요청 스키마"""
    prompt: str = Field(description="사용자 질문")
    user_id: int | None = Field(default=None, description="사용자 ID")

class ChatRequestModel(BaseModel):
    """
    RabbitMQ로 들어오는 프롬프트 메시지 검증용 스키마
    { "userId": 42, "message": "안녕?" }
    또는
    { "user_id": 42, "message": "안녕?" }
    """
    user_id: int = Field(..., alias="userId", description="사용자 ID")
    message: str = Field(description="채팅 메시지")
    session_id: Optional[str] = Field(default=None, description="기존 세션 ID (옵션)")

    model_config = {
        "populate_by_name": True,
    }

class ChatSessionCreateRequest(BaseModel):
    """채팅 세션 생성 요청"""
    title: Optional[str] = Field(default=None, max_length=500, description="세션 제목")
    session_type: str = Field(default="general", max_length=50, description="세션 유형")

class ChatSessionResponse(BaseModel):
    """채팅 세션 응답"""
    id: UUID = Field(description="세션 ID")
    user_id: str = Field(description="사용자 ID")
    title: Optional[str] = Field(description="세션 제목")
    session_type: str = Field(description="세션 유형")
    total_messages: int = Field(description="총 메시지 수")
    last_activity_at: datetime = Field(description="마지막 활동 시간")
    created_at: datetime = Field(description="생성 시간")

class ChatSessionListRequest(BaseModel):
    """채팅 세션 목록 조회 요청"""
    page: int = Field(default=1, ge=1, description="페이지 번호")
    size: int = Field(default=20, ge=1, le=100, description="페이지 크기")
    session_type: Optional[str] = Field(default=None, description="세션 유형 필터")

class ChatSessionUpdateRequest(BaseModel):
    """채팅 세션 업데이트 요청"""
    title: Optional[str] = Field(default=None, max_length=500, description="세션 제목")


class ChatMessageCreateRequest(BaseModel):
    """채팅 메시지 생성 요청"""
    content: str = Field(description="메시지 내용")
    role: str = Field(default="user", description="메시지 역할 (user/assistant)")

class ChatMessageResponse(BaseModel):
    """채팅 메시지 응답"""
    id: UUID = Field(description="메시지 ID")
    session_id: UUID = Field(description="세션 ID")
    user_id: str = Field(description="사용자 ID")
    role: str = Field(description="메시지 역할")
    content: str = Field(description="메시지 내용")
    response_time_ms: Optional[int] = Field(description="응답 시간(ms)")
    created_at: datetime = Field(description="생성 시간")

class ChatStreamRequest(BaseModel):
    """채팅 스트리밍 요청 (기존 로직과 호환)"""
    message: str = Field(description="사용자 메시지")
    session_id: Optional[UUID] = Field(default=None, description="세션 ID (기존 세션 계속하기)")
    user_id: str = Field(description="사용자 ID")

class ChatStreamResponse(BaseModel):
    """채팅 스트리밍 응답"""
    session_id: UUID = Field(description="세션 ID")
    message_id: UUID = Field(description="메시지 ID")
    answer: str = Field(description="AI 응답")
    graph_payload: Dict[str, Any] = Field(description="그래프 데이터")
    rag_metadata: Optional[Dict[str, Any]] = Field(default=None, description="RAG 메타데이터")

# RAG 관련 스키마
class RAGSearchResult(BaseModel):
    """RAG 검색 결과"""
    chunk_id: str = Field(description="청크 ID")
    bookmark_id: UUID = Field(description="북마크 ID")
    similarity_score: float = Field(description="유사도 점수")
    chunk_preview: str = Field(description="청크 미리보기")
    bookmark_title: Optional[str] = Field(description="북마크 제목")
    bookmark_url: Optional[str] = Field(description="북마크 URL")

class RAGMetadata(BaseModel):
    """RAG 메타데이터"""
    search_query: Dict[str, str] = Field(description="검색 쿼리 정보")
    retrieval_results: List[RAGSearchResult] = Field(description="검색 결과")
    search_performance: Dict[str, Any] = Field(description="검색 성능 정보")
    llm_metadata: Dict[str, Any] = Field(description="LLM 메타데이터")

# 피드백 관련 스키마
class ChatFeedbackRequest(BaseModel):
    """채팅 피드백 요청"""
    message_id: UUID = Field(description="메시지 ID")
    feedback_type: str = Field(description="피드백 유형 (helpful/not_helpful/partially_helpful)")
    feedback_score: int = Field(ge=1, le=5, description="피드백 점수 (1-5)")
    comment: Optional[str] = Field(default=None, description="피드백 댓글")
    helpful_chunks: Optional[List[str]] = Field(default=None, description="도움이 된 청크 ID들")
    irrelevant_chunks: Optional[List[str]] = Field(default=None, description="관련없는 청크 ID들")

class ChatFeedbackResponse(BaseModel):
    """채팅 피드백 응답"""
    id: UUID = Field(description="피드백 ID")
    message_id: UUID = Field(description="메시지 ID")
    feedback_type: str = Field(description="피드백 유형")
    feedback_score: int = Field(description="피드백 점수")
    created_at: datetime = Field(description="생성 시간")
