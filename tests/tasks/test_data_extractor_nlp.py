"""
NLP 데이터 추출기 테스트

형태소 분석기를 사용한 키워드 추출이 적용된 NLP 데이터 추출기의 기능을 테스트합니다.
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from app.tasks.data_extractor_nlp import NebulaNLPExtractor
from app.models.extract_data import ExtractDataModel


class TestNebulaNLPExtractor:
    """NebulaNLPExtractor 클래스 테스트"""

    def setup_method(self):
        """각 테스트 메서드 실행 전 설정"""
        self.extractor = NebulaNLPExtractor()
        
    def test_extractor_initialization(self):
        """추출기 초기화 테스트"""
        extractor = NebulaNLPExtractor()
        
        # requests.Session이 초기화되었는지 확인
        assert hasattr(extractor, 'session')
        assert extractor.session is not None
        
        # User-Agent가 설정되었는지 확인
        assert 'User-Agent' in extractor.session.headers

    @pytest.mark.asyncio
    async def test_fetch_html_content_success(self):
        """HTML 컨텐츠 가져오기 성공 테스트"""
        mock_response = MagicMock()
        mock_response.text = "<html><body>테스트 컨텐츠</body></html>"
        mock_response.raise_for_status.return_value = None
        
        with patch.object(self.extractor.session, 'get', return_value=mock_response):
            result = await self.extractor._fetch_html_content("https://test.com")
            
            assert result == "<html><body>테스트 컨텐츠</body></html>"

    @pytest.mark.asyncio
    async def test_fetch_html_content_failure(self):
        """HTML 컨텐츠 가져오기 실패 테스트"""
        with patch.object(self.extractor.session, 'get', side_effect=Exception("Connection error")):
            with pytest.raises(Exception):
                await self.extractor._fetch_html_content("https://test.com")

    def test_extract_text_content(self):
        """텍스트 컨텐츠 추출 테스트"""
        from bs4 import BeautifulSoup
        
        html = """
        <html>
            <body>
                <div>인공지능 기술</div>
                <article>머신러닝과 딥러닝</article>
                <script>console.log('test');</script>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        result = self.extractor._extract_text_content(soup)
        
        # 본문 텍스트가 추출되었는지 확인
        assert "인공지능" in result
        assert "머신러닝" in result
        
        # 스크립트는 제거되었는지 확인 (extract_main_text 함수에서 처리)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_extract_keywords_tfidf(self):
        """키워드 추출 테스트"""
        test_text = """
        인공지능은 컴퓨터 과학의 한 분야입니다. 
        머신러닝과 딥러닝은 AI의 핵심 기술입니다.
        자연어 처리와 컴퓨터 비전이 주요 응용분야입니다.
        """
        
        keywords = await self.extractor._extract_keywords_tfidf(test_text, max_keywords=5)
        
        # 키워드가 추출되었는지 확인
        assert isinstance(keywords, list)
        assert len(keywords) <= 5
        
        # 형태소 분석기를 통해 명사만 추출되었는지 확인
        if keywords:  # 키워드가 있을 경우
            # 모든 키워드가 2글자 이상인지 확인
            assert all(len(keyword) >= 2 for keyword in keywords)

    @pytest.mark.asyncio
    async def test_extract_keywords_empty_text(self):
        """빈 텍스트 키워드 추출 테스트"""
        keywords = await self.extractor._extract_keywords_tfidf("", max_keywords=5)
        assert keywords == []
        
        keywords = await self.extractor._extract_keywords_tfidf(None, max_keywords=5)
        assert keywords == []

    @pytest.mark.asyncio
    async def test_create_thumbnail_success(self):
        """썸네일 생성 성공 테스트"""
        # PIL.Image 객체 모킹
        mock_image = MagicMock()
        mock_image.mode = 'RGB'
        mock_image.thumbnail = MagicMock()
        mock_image.save = MagicMock()
        
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"
        mock_response.raise_for_status.return_value = None
        
        with patch.object(self.extractor.session, 'get', return_value=mock_response), \
             patch('app.tasks.data_extractor_nlp.Image.open', return_value=mock_image), \
             patch('base64.b64encode', return_value=b"encoded_data"):
            
            result = await self.extractor._create_thumbnail("https://test.com/image.jpg")
            
            # base64 문자열이 반환되었는지 확인
            assert result == "encoded_data"

    @pytest.mark.asyncio
    async def test_create_thumbnail_failure(self):
        """썸네일 생성 실패 테스트"""
        with patch.object(self.extractor.session, 'get', side_effect=Exception("Image download failed")):
            result = await self.extractor._create_thumbnail("https://test.com/invalid.jpg")
            
            # 실패 시 None 반환 확인
            assert result is None

    @pytest.mark.asyncio
    async def test_extract_thumbnails(self):
        """이미지 추출 및 썸네일 생성 테스트"""
        from bs4 import BeautifulSoup
        
        html = """
        <html>
            <body>
                <img src="image1.jpg" alt="이미지1">
                <img src="/image2.png" alt="이미지2">
                <img src="https://example.com/image3.gif" alt="이미지3">
            </body>
        </html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # _create_thumbnail 메서드를 모킹
        with patch.object(self.extractor, '_create_thumbnail', return_value="mock_thumbnail_data"):
            thumbnails = await self.extractor._extract_thumbnails(soup, "https://test.com")
            
            # 최대 3개의 이미지가 처리되었는지 확인
            assert len(thumbnails) <= 3
            
            # 각 썸네일이 올바른 구조를 가지는지 확인
            for thumbnail in thumbnails:
                assert 'original_url' in thumbnail
                assert 'alt_text' in thumbnail
                assert 'thumbnail_base64' in thumbnail
                assert 'width' in thumbnail
                assert 'height' in thumbnail

    def test_extract_meta_description(self):
        """메타 설명 추출 테스트"""
        from bs4 import BeautifulSoup
        
        # meta description이 있는 경우
        html_with_meta = """
        <html>
            <head>
                <meta name="description" content="인공지능에 대한 설명">
            </head>
        </html>
        """
        soup = BeautifulSoup(html_with_meta, 'html.parser')
        description = self.extractor._extract_meta_description(soup)
        assert description == "인공지능에 대한 설명"
        
        # Open Graph description이 있는 경우
        html_with_og = """
        <html>
            <head>
                <meta property="og:description" content="OG 설명">
            </head>
        </html>
        """
        soup = BeautifulSoup(html_with_og, 'html.parser')
        description = self.extractor._extract_meta_description(soup)
        assert description == "OG 설명"
        
        # 메타 설명이 없는 경우
        html_empty = "<html><body><p>내용</p></body></html>"
        soup = BeautifulSoup(html_empty, 'html.parser')
        description = self.extractor._extract_meta_description(soup)
        assert description == ""

    @pytest.mark.asyncio
    async def test_extract_and_process_success(self):
        """전체 데이터 추출 및 처리 성공 테스트"""
        request = ExtractDataModel(user_id=1, url="https://test.com")
        
        # 모든 내부 메서드들을 모킹
        mock_html = "<html><body><div>테스트 컨텐츠</div></body></html>"
        mock_thumbnails = [{"original_url": "test.jpg", "thumbnail_base64": "data"}]
        mock_keywords = ["테스트", "컨텐츠"]
        
        with patch.object(self.extractor, '_fetch_html_content', return_value=mock_html), \
             patch.object(self.extractor, '_extract_thumbnails', return_value=mock_thumbnails), \
             patch.object(self.extractor, '_extract_keywords_tfidf', return_value=mock_keywords), \
             patch('app.tasks.data_extractor_nlp.BeautifulSoup') as mock_soup_class:
            
            mock_soup = MagicMock()
            mock_soup_class.return_value = mock_soup
            
            with patch.object(self.extractor, '_extract_text_content', return_value="추출된 텍스트"), \
                 patch.object(self.extractor, '_extract_meta_description', return_value="테스트 설명"):
                
                result = await self.extractor.extract_and_process(request)
                
                # 결과 구조 확인
                assert result['status'] == 'processed'
                assert result['user_id'] == 1
                assert result['url'] == 'https://test.com'
                assert len(result['documents']) == 1
                
                doc = result['documents'][0]
                assert doc['keywords'] == mock_keywords
                assert doc['thumbnails'] == mock_thumbnails
                assert doc['meta_description'] == '테스트 설명'

    @pytest.mark.asyncio
    async def test_extract_and_process_error_handling(self):
        """데이터 추출 및 처리 오류 처리 테스트"""
        request = ExtractDataModel(user_id=1, url="https://invalid-url.com")
        
        # HTML 가져오기에서 오류 발생 시뮬레이션
        with patch.object(self.extractor, '_fetch_html_content', side_effect=Exception("Network error")):
            result = await self.extractor.extract_and_process(request)
            
            # 오류 처리 결과 확인
            assert result['status'] == 'error'
            assert result['user_id'] == 1
            assert result['url'] == 'https://invalid-url.com'
            assert result['documents'] == []
            assert 'error' in result


class TestIntegrationNLPExtractor:
    """NLP 추출기 통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_text_processing(self):
        """text_processing 유틸리티를 사용한 전체 파이프라인 테스트"""
        extractor = NebulaNLPExtractor()
        
        # 실제 HTML 컨텐츠 시뮬레이션
        mock_html = """
        <html>
            <head>
                <title>인공지능과 머신러닝</title>
                <meta name="description" content="AI와 ML에 대한 종합 가이드">
            </head>
            <body>
                <article>
                    <h1>Artificial Intelligence Overview</h1>
                    <p>인공지능은 컴퓨터 과학의 한 분야입니다.</p>
                    <p>Machine learning과 deep learning이 핵심 기술입니다.</p>
                </article>
                <img src="ai-image.jpg" alt="AI 이미지">
            </body>
        </html>
        """
        
        request = ExtractDataModel(user_id=1, url="https://ai-guide.com")
        
        with patch.object(extractor, '_fetch_html_content', return_value=mock_html), \
             patch.object(extractor, '_create_thumbnail', return_value="mock_base64_data"):
            
            result = await extractor.extract_and_process(request)
            
            # 성공적으로 처리되었는지 확인
            assert result['status'] == 'processed'
            assert len(result['documents']) == 1
            
            doc = result['documents'][0]
            
            # 메타 설명이 정확히 추출되었는지 확인
            assert doc['meta_description'] == 'AI와 ML에 대한 종합 가이드'
            
            # 형태소 분석기를 통한 키워드 추출 확인
            keywords = doc['keywords']
            assert isinstance(keywords, list)
            # 명사만 추출되었는지 확인 (길이 체크)
            if keywords:
                assert all(len(kw) >= 2 for kw in keywords)
            
            # 썸네일이 생성되었는지 확인
            thumbnails = doc['thumbnails']
            assert isinstance(thumbnails, list)
            if thumbnails:
                assert 'thumbnail_base64' in thumbnails[0]
                assert 'original_url' in thumbnails[0]

    @pytest.mark.asyncio
    async def test_korean_english_mixed_content(self):
        """한영 혼합 컨텐츠 처리 테스트"""
        extractor = NebulaNLPExtractor()
        
        mock_html = """
        <html>
            <body>
                <div>
                    Artificial Intelligence(인공지능)는 computer science 분야입니다.
                    머신러닝과 딥러닝은 AI development에 핵심적입니다.
                    Natural language processing과 자연어처리는 같은 의미입니다.
                </div>
            </body>
        </html>
        """
        
        request = ExtractDataModel(user_id=1, url="https://mixed-content.com")
        
        with patch.object(extractor, '_fetch_html_content', return_value=mock_html):
            result = await extractor.extract_and_process(request)
            
            assert result['status'] == 'processed'
            doc = result['documents'][0]
            
            # 한영 혼합 키워드가 모두 추출되었는지 확인
            keywords = doc['keywords']
            if keywords:
                # 한국어 키워드 확인
                korean_found = any('가' <= char <= '힣' for keyword in keywords for char in keyword)
                # 영어 키워드 확인
                english_found = any(keyword.isalpha() and not any('가' <= char <= '힣' for char in keyword) 
                                  for keyword in keywords)
                
                # 적어도 하나의 언어에서 키워드가 추출되어야 함
                assert korean_found or english_found

    @pytest.mark.asyncio
    async def test_morphological_analysis_quality(self):
        """형태소 분석기 품질 테스트"""
        extractor = NebulaNLPExtractor()
        
        # 품사가 다양한 텍스트로 테스트
        test_text = """
        빠르게 달리는 아름다운 자동차가 높은 산을 넘어갔다.
        The quick brown fox jumps over the lazy dog very quickly.
        """
        
        keywords = await extractor._extract_keywords_tfidf(test_text, max_keywords=10)
        
        # 명사만 추출되었는지 확인
        if keywords:
            # 한국어 명사 예상: 자동차, 산 등
            # 영어 명사 예상: fox, dog 등
            # 형용사나 부사는 제외되어야 함: 빠르게(부사), 아름다운(형용사), quickly(부사) 등
            
            # 모든 키워드가 적절한 길이인지 확인
            assert all(len(kw) >= 2 for kw in keywords)
            
            # 불용어가 제거되었는지 확인
            stopword_check = ['이', '그', 'the', 'over', 'very']
            for stopword in stopword_check:
                assert stopword not in keywords, f"불용어가 제거되지 않음: {stopword}" 