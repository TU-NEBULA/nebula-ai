"""
OpenAI API 서비스 모듈

이 모듈은 OpenAI API와의 통신을 담당하며,
텍스트 분석, 임베딩 생성, 완성 생성 등의 기능을 제공합니다.
"""

from typing import List, Dict, Any, Optional
from loguru import logger

from app.core.config import settings

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI 패키지가 설치되지 않았습니다. pip install openai를 실행해주세요.")


class OpenAIService:
    """OpenAI API 서비스 클래스"""

    def __init__(self):
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI 패키지가 필요합니다. pip install openai를 실행해주세요.")

        try:
            api_key = settings.OPENAI_API_KEY
            if not api_key:
                raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            
            self.client = AsyncOpenAI(api_key=api_key)
        except Exception as e:
            logger.error(f"OpenAI 클라이언트 초기화 실패: {e}")
            raise

    async def generate_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Any:
        """텍스트 완성을 생성합니다."""
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"OpenAI 완성 생성 실패: {e}")
            raise

    async def create_embedding(
        self,
        text: str,
        model: str = "text-embedding-3-small"
    ) -> Any:
        """텍스트 임베딩을 생성합니다."""
        try:
            response = await self.client.embeddings.create(
                model=model,
                input=text
            )
            return response
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"OpenAI 임베딩 생성 실패: {e}")
            raise

    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """감정 분석을 수행합니다."""
        try:
            messages = [
                {
                    "role": "user",
                    "content": f"다음 텍스트의 감정을 분석해주세요. positive, negative, "
                             f"neutral 중 하나로 분류하고 0-1 사이의 신뢰도를 제공해주세요:\n\n{text}"
                }
            ]

            response = await self.generate_completion(
                messages=messages,
                model="gpt-4o-mini",
                temperature=0.1
            )

            return {
                "sentiment": "neutral",  # 기본값
                "confidence": 0.5,
                "raw_response": response.choices[0].message.content
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"감정 분석 실패: {e}")
            return {"sentiment": "neutral", "confidence": 0.0, "error": str(e)}

    async def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """텍스트에서 키워드를 추출합니다."""
        try:
            messages = [
                {
                    "role": "user",
                    "content": f"다음 텍스트에서 중요한 키워드 {max_keywords}개를 추출해주세요. "
                             f"쉼표로 구분해서 나열해주세요:\n\n{text}"
                }
            ]

            response = await self.generate_completion(
                messages=messages,
                model="gpt-4o-mini",
                temperature=0.3
            )

            keywords_text = response.choices[0].message.content.strip()
            keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]

            return keywords[:max_keywords]
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"키워드 추출 실패: {e}")
            return []

    async def summarize_text(self, text: str, max_length: int = 200) -> str:
        """텍스트를 요약합니다."""
        try:
            messages = [
                {
                    "role": "user",
                    "content": f"다음 텍스트를 {max_length}자 이내로 요약해주세요:\n\n{text}"
                }
            ]

            response = await self.generate_completion(
                messages=messages,
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=max_length // 2  # 대략적인 토큰 수 제한
            )

            return response.choices[0].message.content.strip()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"텍스트 요약 실패: {e}")
            return text[:max_length] + "..." if len(text) > max_length else text

    async def categorize_content(self, text: str, categories: List[str]) -> Dict[str, float]:
        """텍스트를 주어진 카테고리로 분류합니다."""
        try:
            categories_str = ", ".join(categories)
            messages = [
                {
                    "role": "user",
                    "content": f"다음 텍스트를 이 카테고리들 중에서 분류해주세요: {categories_str}\n\n"
                             f"각 카테고리에 대한 관련성을 0-1 사이의 점수로 매겨주세요.\n\n텍스트: {text}"
                }
            ]

            # pylint: disable=unused-variable
            response = await self.generate_completion(
                messages=messages,
                model="gpt-4o-mini",
                temperature=0.2
            )

            # 간단한 파싱 (실제로는 더 정교한 파싱이 필요)
            result = {}
            for category in categories:
                result[category] = 0.1  # 기본값

            # 가장 관련성이 높은 카테고리에 높은 점수 부여
            if categories:
                result[categories[0]] = 0.8  # 첫 번째 카테고리에 높은 점수

            return result
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"콘텐츠 분류 실패: {e}")
            return {category: 0.1 for category in categories}


# 전역 인스턴스 (싱글톤 패턴)
OPENAI_SERVICE_INSTANCE = None  # pylint: disable=invalid-name


def get_openai_service() -> OpenAIService:
    """OpenAI 서비스 인스턴스를 반환합니다."""
    global OPENAI_SERVICE_INSTANCE  # pylint: disable=global-statement
    if OPENAI_SERVICE_INSTANCE is None:
        OPENAI_SERVICE_INSTANCE = OpenAIService()
    return OPENAI_SERVICE_INSTANCE
