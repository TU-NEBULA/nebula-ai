"""
Nebula NLP 데이터 추출기
"""

import io
import base64
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
import requests
from PIL import Image
from bs4 import BeautifulSoup
from loguru import logger
from app.models.extract_data import ExtractDataModel
from app.utils.text_processing import (
    extract_main_text, 
    extract_keywords, 
    smart_keyword_extraction,
    generate_text_summary
)


class NebulaNLPExtractor:
    """
    Nebula AI NLP 데이터 추출기
    """

    def __init__(self):
        """초기화"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

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
            thumbnails = await self._extract_thumbnails(soup, request.url)
            
            # 텍스트 추출
            text_content = self._extract_text_content(soup)
            
            # TF-IDF를 사용한 키워드 추출
            keywords = await self._extract_keywords_tfidf(text_content)
            
            # 결과 구성
            result = {
                "user_id": request.user_id,
                "url": request.url,
                "documents": [{
                    "title": self._extract_title(soup),
                    "content": text_content[:1000] if text_content else "",  # 첫 1000자만
                    "keywords": keywords,
                    "thumbnails": thumbnails,
                    "meta_description": self._extract_meta_description(soup)
                }],
                "status": "processed"
            }

        except Exception as e:
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
        except Exception as e:
            logger.error(f"HTML 컨텐츠 가져오기 실패: {url}, error: {str(e)}")
            raise

    async def _extract_thumbnails(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
        """이미지 추출 및 썸네일 생성"""
        thumbnails = []
        images = soup.find_all('img', src=True)
        
        # 최대 3개의 이미지만 처리
        for img in images[:3]:
            try:
                img_url = img.get('src')
                if not img_url:
                    continue
                
                # 상대 URL을 절대 URL로 변환
                img_url = urljoin(base_url, img_url)
                
                # 이미지 다운로드 및 썸네일 생성
                thumbnail_data = await self._create_thumbnail(img_url)
                if thumbnail_data:
                    thumbnails.append({
                        "original_url": img_url,
                        "alt_text": img.get('alt', ''),
                        "thumbnail_base64": thumbnail_data,
                        "width": 150,  # 썸네일 크기
                        "height": 150
                    })
                    
            except Exception as e:
                logger.warning(f"이미지 처리 실패: {img_url}, error: {str(e)}")
                continue
        
        return thumbnails

    async def _create_thumbnail(self, img_url: str) -> Optional[str]:
        """이미지 썸네일 생성"""
        try:
            # 이미지 다운로드
            response = self.session.get(img_url, timeout=5)
            response.raise_for_status()
            
            # 이미지 열기
            image = Image.open(io.BytesIO(response.content))
            
            # RGB로 변환 (RGBA나 다른 모드인 경우)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 썸네일 생성 (150x150)
            image.thumbnail((150, 150), Image.Resampling.LANCZOS)
            
            # Base64로 인코딩
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return image_base64
            
        except Exception as e:
            logger.warning(f"썸네일 생성 실패: {img_url}, error: {str(e)}")
            return None

    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """텍스트 컨텐츠 추출"""
        # HTML을 문자열로 변환하여 extract_main_text 함수 사용
        html_content = str(soup)
        return extract_main_text(html_content)

    async def _extract_keywords_tfidf(self, text: str, max_keywords: int = 3) -> List[str]:
        """TF-IDF를 사용한 키워드 추출"""
        if not text:
            return []
        
        try:
            # text_processing.py의 extract_keywords 함수 사용
            keywords = extract_keywords(text, max_keywords)
            return keywords
            
        except Exception as e:
            logger.error(f"키워드 추출 실패: {str(e)}")
            return []

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """페이지 제목 추출"""
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()
        
        # title 태그가 없으면 h1 태그 시도
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text().strip()
        
        return "제목 없음"

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
    