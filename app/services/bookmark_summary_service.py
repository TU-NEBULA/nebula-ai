"""
북마크 요약 서비스

북마크 내용을 OpenAI를 사용해 요약하고 SSE로 스트리밍하는 서비스입니다.
"""

import json
import time
from typing import AsyncGenerator, List, Optional, Dict, Any
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.repositories.vector_repository import VectorRepository
from app.external.openai_service import OpenAIService
from app.external.s3_service import download_html_from_s3, download_html_from_url
from app.utils.text_processing import extract_main_text
from app.schemas.bookmark_summary_schemas import (
    BookmarkSummaryRequest,
    BookmarkSummaryProgress,
    BookmarkSummaryResult,
    BookmarkSummaryError,
    SSEEventType
)


class BookmarkSummaryService:
    """북마크 요약 서비스"""
    
    def __init__(self):
        self.openai_service = OpenAIService()
    
    async def generate_summary_stream(
        self, 
        request: BookmarkSummaryRequest
    ) -> AsyncGenerator[str, None]:
        """
        북마크 요약을 챗봇 SSE와 동일하게 data: {"type": ...} JSON으로 토큰 단위 스트리밍합니다.
        """
        import json
        start_time = time.time()
        summary_content = ""
        try:
            body_text = await self._download_and_extract_content(request)
            if not body_text or not body_text.strip():
                error_obj = {
                    "type": "error",
                    "data": {
                        "error_code": "CONTENT_EXTRACTION_FAILED",
                        "error_message": "본문 추출에 실패했습니다.",
                        "url": request.url,
                        "s3_key": request.s3_key
                    }
                }
                yield f"data: {json.dumps(error_obj, ensure_ascii=False)}\n\n"
                return
            total_characters = len(body_text)
            async for summary_chunk in self._generate_summary_streaming(
                body_text, 
                request
            ):
                summary_content += summary_chunk
                chunk_obj = {
                    "type": "chunk",
                    "data": summary_chunk,
                    "content": summary_chunk
                }
                yield f"data: {json.dumps(chunk_obj, ensure_ascii=False)}\n\n"
            processing_time = time.time() - start_time
            result = BookmarkSummaryResult(
                url=request.url,
                s3_key=request.s3_key,
                summary=summary_content,
                total_characters=total_characters,
                summary_length=len(summary_content),
                processing_time=processing_time
            )
            complete_obj = {
                "type": "complete",
                "data": result.dict()
            }
            yield f"data: {json.dumps(complete_obj, ensure_ascii=False)}\n\n"
        except Exception as e:
            error_obj = {
                "type": "error",
                "data": {
                    "error_code": "SUMMARY_GENERATION_ERROR",
                    "error_message": f"요약 생성 중 오류가 발생했습니다: {str(e)}",
                    "url": request.url,
                    "s3_key": request.s3_key
                }
            }
            yield f"data: {json.dumps(error_obj, ensure_ascii=False)}\n\n"
        finally:
            end_obj = {"type": "end", "data": {}}
            yield f"data: {json.dumps(end_obj, ensure_ascii=False)}\n\n"

    async def _download_and_extract_content(self, request: BookmarkSummaryRequest) -> str:
        # S3 우선, 없으면 URL
        if request.s3_key:
            try:
                html = download_html_from_s3(request.s3_key)
                return extract_main_text(html)
            except Exception as e:
                logger.warning(f"S3에서 HTML 다운로드 실패: {e}")
        if request.url:
            try:
                html = download_html_from_url(request.url)
                return extract_main_text(html)
            except Exception as e:
                logger.warning(f"URL에서 HTML 다운로드 실패: {e}")
        return ""

    async def _generate_summary_streaming(
        self, 
        content: str, 
        request: BookmarkSummaryRequest
    ) -> AsyncGenerator[str, None]:
        """
        OpenAI를 사용해 내용을 스트리밍으로 요약합니다.
        
        Args:
            content: 요약할 내용
            request: 요약 요청 정보
            
        Yields:
            요약 텍스트 청크들
        """
        # 요약 프롬프트 생성
        prompt = self._build_summary_prompt(content, request)
        
        try:
            # OpenAI 스트리밍 호출
            response = await self.openai_service.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 웹 페이지 내용을 요약하는 전문가입니다. 사용자가 요청한 형식에 맞춰 명확하고 유용한 요약을 제공해주세요."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=request.max_length * 2,  # 여유분 고려
                stream=True
            )
            
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenAI 요약 생성 오류: {e}")
            yield f"요약 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _build_summary_prompt(
        self, 
        content: str, 
        request: BookmarkSummaryRequest
    ) -> str:
        """
        요약을 위한 프롬프트를 생성합니다.
        
        Args:
            content: 요약할 내용
            request: 요약 요청
            
        Returns:
            생성된 프롬프트
        """
        language_instruction = {
            "ko": "한국어로",
            "en": "in English"
        }.get(request.language, "한국어로")
        return f"""
다음 웹 페이지 내용을 주요 포인트를 포함하여 자세히 {language_instruction} 요약해주세요. 최대 {request.max_length}자 이내로 작성해주세요.\n\n웹 페이지 내용:\n{content[:8000]}\n\n요약할 때 다음 사항을 고려해주세요:\n- 핵심 내용과 주요 포인트를 중심으로 요약\n- 불필요한 광고나 네비게이션 텍스트는 제외\n- 읽기 쉽고 이해하기 쉬운 형태로 구성\n- 원본의 의도와 맥락을 유지\n"""
    
    async def _extract_keywords(self, content: str) -> List[str]:
        """
        내용에서 키워드를 추출합니다.
        
        Args:
            content: 키워드를 추출할 내용
            
        Returns:
            추출된 키워드 리스트
        """
        try:
            keywords = await self.openai_service.extract_keywords(
                content[:4000],  # 너무 긴 내용은 잘라서 처리
                max_keywords=10
            )
            return keywords
        except Exception as e:
            logger.error(f"키워드 추출 오류: {e}")
            return [] 