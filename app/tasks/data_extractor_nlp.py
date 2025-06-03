"""
Nebula NLP 데이터 추출기
"""

from typing import Dict, Any, List
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from loguru import logger
from app.models.extract_data import ExtractDataModel
from app.core.config import settings
from app.utils.text_processing import (
    extract_main_text,
    smart_keyword_extraction
)


class NebulaNLPExtractor:  # pylint: disable=too-few-public-methods
    """
    Nebula AI NLP 데이터 추출기
    """

    def __init__(self):
        """초기화"""
        self.session = requests.Session()
        user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/91.0.4472.124 Safari/537.36'
        )
        self.session.headers.update({'User-Agent': user_agent})

    async def extract_and_process(self, request: ExtractDataModel) -> Dict[str, Any]:
        """
        데이터 추출 및 처리

        Args:
            request: 추출 요청 모델

        Returns:
            처리 결과 딕셔너리
        """
        logger.info(f"🔍 데이터 추출 처리 시작 - user_id: {request.user_id}, url: {request.url}")

        try:
            # HTML 컨텐츠 가져오기
            html_content = await self._fetch_html_content(request.url)

            # HTML 파싱
            soup = BeautifulSoup(html_content, 'html.parser')

            # 이미지 추출 및 썸네일 생성
            thumbnail = self._extract_thumbnail(soup, request.url)

            # 텍스트 추출
            text_content = self._extract_text_content(soup)

            # TF-IDF를 사용한 키워드 추출
            keywords = await self._extract_keywords_tfidf(text_content, request.user_id)

            # 결과 구성
            result = {
                "user_id": request.user_id,
                "url": request.url,
                "documents": [{
                    "content": text_content[:1000] if text_content else "",  # 첫 1000자만
                    "keywords": keywords,
                    "thumbnail": thumbnail,
                    "meta_description": self._extract_meta_description(soup)
                }],
                "status": "processed"
            }

        except (requests.RequestException, ValueError, TypeError) as e:
            logger.error(f"❌ 데이터 추출 처리 중 오류 발생 - user_id: {request.user_id}, error: {str(e)}")
            result = {
                "user_id": request.user_id,
                "url": request.url,
                "documents": [],
                "status": "error",
                "error": str(e)
            }

        logger.info(f"✅ 데이터 추출 처리 완료 - user_id: {request.user_id}")
        return result

    async def _fetch_html_content(self, url: str) -> str:
        """HTML 컨텐츠 가져오기"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"HTML 컨텐츠 가져오기 실패: {url}, error: {str(e)}")
            raise

    def _extract_thumbnail(self, soup: BeautifulSoup, base_url: str) -> str:
        """이미지 URL 추출"""
        # 우선순위에 따른 이미지 추출
        # 1. Open Graph 이미지
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image and og_image.get('content'):
            img_url = og_image.get('content')
            if not img_url.startswith('http'):
                img_url = urljoin(base_url, img_url)
            return img_url

        # 2. 첫 번째 img 태그
        first_img = soup.find('img', src=True)
        if first_img:
            img_url = first_img.get('src')
            if img_url:
                # 상대 URL을 절대 URL로 변환
                if not img_url.startswith('http'):
                    img_url = urljoin(base_url, img_url)
                return img_url

        # 3. 썸네일이 없는 경우 기본 이미지 사용
        return settings.BASE_THUMBNAIL

    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """텍스트 컨텐츠 추출"""
        # HTML을 문자열로 변환하여 extract_main_text 함수 사용
        html_content = str(soup)
        return extract_main_text(html_content)

    async def _extract_keywords_tfidf(
        self, text: str, user_id: str, max_keywords: int = 3
    ) -> List[str]:
        """TF-IDF를 사용한 키워드 추출"""
        if not text:
            return []

        try:
            keywords = await smart_keyword_extraction(text, user_id, max_keywords)
            return keywords

        except (ValueError, TypeError) as e:
            logger.error(f"키워드 추출 실패: {str(e)}")
            return []

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        """메타 설명 추출"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc.get('content').strip()

        # Open Graph description 시도
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc and og_desc.get('content'):
            return og_desc.get('content').strip()

        return ""
