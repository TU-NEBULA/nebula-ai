"""
Nebula NLP 데이터 추출기
"""

from typing import Dict, Any, List
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from loguru import logger
from app.models.extract_data import ExtractDataRequest
from app.external.s3_service import download_html_from_s3
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

    async def extract_and_process(self, request: ExtractDataRequest) -> Dict[str, Any]:
        """
        데이터 추출 및 처리

        Args:
            request: 추출 요청 모델 (url, s3_key 포함)

        Returns:
            처리 결과 딕셔너리
        """
        logger.info(f"🔍 데이터 추출 처리 시작 - user_id: {request.user_id}, url: {request.url}, s3_key: {request.s3_key}")

        try:
            # S3에서 HTML 컨텐츠 가져오기
            html_content = await self._fetch_html_from_s3(request.s3_key)

            # HTML 파싱
            soup = BeautifulSoup(html_content, 'html.parser')

            # 이미지 추출 및 썸네일 생성 (원본 URL 사용)
            thumbnail = self._extract_thumbnail(soup, request.url)

            # 텍스트 추출
            text_content = self._extract_text_content(soup)

            # TF-IDF를 사용한 키워드 추출
            keywords = await self._extract_keywords_tfidf(text_content, request.user_id)

            # 결과 구성
            result = {
                "user_id": request.user_id,
                "url": request.url,
                "s3_key": request.s3_key,
                "documents": [{
                    "content": text_content[:1000] if text_content else "",  # 첫 1000자만
                    "keywords": keywords,
                    "thumbnail": thumbnail,
                    "meta_description": self._extract_meta_description(soup)
                }],
                "status": "processed"
            }

        except (requests.RequestException, ValueError, TypeError, Exception) as e:
            logger.error(f"❌ 데이터 추출 처리 중 오류 발생 - user_id: {request.user_id}, error: {str(e)}")
            result = {
                "user_id": request.user_id,
                "url": request.url,
                "s3_key": request.s3_key,
                "documents": [],
                "status": "error",
                "error": str(e)
            }

        logger.info(f"✅ 데이터 추출 처리 완료 - user_id: {request.user_id}")
        return result

    async def _fetch_html_from_s3(self, s3_key: str) -> str:
        """S3에서 HTML 컨텐츠 가져오기"""
        try:
            html_content = download_html_from_s3(s3_key)
            logger.info(f"✅ S3에서 HTML 다운로드 성공: {s3_key}")
            return html_content
        except Exception as e:
            logger.error(f"❌ S3에서 HTML 다운로드 실패: {s3_key}, error: {str(e)}")
            raise

    async def _fetch_html_content(self, url: str) -> str:
        """HTML 컨텐츠 가져오기 (기존 URL 방식, 필요시 사용)"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"HTML 컨텐츠 가져오기 실패: {url}, error: {str(e)}")
            raise

    def _extract_thumbnail(self, soup: BeautifulSoup, base_url: str = None) -> str:
        """이미지 URL 추출"""
        # 우선순위에 따른 이미지 추출
        # 1. Open Graph 이미지
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image and og_image.get('content'):
            img_url = og_image.get('content')
            # base_url이 있을 때만 절대 URL 변환
            if base_url and not img_url.startswith('http'):
                img_url = urljoin(base_url, img_url)
            return img_url

        # 2. 첫 번째 img 태그
        first_img = soup.find('img', src=True)
        if first_img:
            img_url = first_img.get('src')
            if img_url:
                # base_url이 있을 때만 상대 URL을 절대 URL로 변환
                if base_url and not img_url.startswith('http'):
                    img_url = urljoin(base_url, img_url)
                return img_url

        # 3. 썸네일이 없는 경우 기본 이미지 사용
        return settings.BASE_THUMBNAIL

    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """텍스트 컨텐츠 추출"""
        # HTML을 문자열로 변환하여 extract_main_text 함수 사용
        html_content = str(soup)
        logger.debug(f"📄 HTML 길이: {len(html_content)}")
        
        text_content = extract_main_text(html_content)
        logger.info(f"📝 추출된 텍스트 길이: {len(text_content) if text_content else 0}")
        
        if text_content and len(text_content) > 100:
            logger.debug(f"📝 텍스트 샘플 (첫 200자): {text_content[:200]}...")
        elif text_content:
            logger.debug(f"📝 전체 텍스트: {text_content}")
        else:
            logger.warning("⚠️ 텍스트 추출 실패 - 빈 결과")
            
        return text_content

    async def _extract_keywords_tfidf(
        self, text: str, user_id: str, max_keywords: int = 3
    ) -> List[str]:
        """TF-IDF를 사용한 키워드 추출"""
        logger.info(f"🔍 키워드 추출 시작 - user_id: {user_id}, 텍스트 길이: {len(text) if text else 0}")
        
        if not text:
            logger.warning(f"⚠️ 빈 텍스트로 인한 키워드 추출 불가 - user_id: {user_id}")
            return []

        if len(text.strip()) < 10:
            logger.warning(f"⚠️ 텍스트가 너무 짧음 (길이: {len(text.strip())}) - user_id: {user_id}")
            return []

        try:
            logger.debug(f"📝 텍스트 샘플 (첫 200자) - user_id: {user_id}: {text[:200]}...")
            keywords = await smart_keyword_extraction(text, user_id, max_keywords)
            
            if keywords:
                logger.info(f"✅ 키워드 추출 성공 - user_id: {user_id}, 키워드 수: {len(keywords)}, 키워드: {keywords}")
            else:
                logger.warning(f"⚠️ smart_keyword_extraction에서 빈 결과 반환 - user_id: {user_id}")
                
            return keywords

        except Exception as e:
            logger.error(f"❌ 키워드 추출 중 예외 발생 - user_id: {user_id}, 오류: {str(e)}")
            logger.exception(f"키워드 추출 예외 상세 - user_id: {user_id}")
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
