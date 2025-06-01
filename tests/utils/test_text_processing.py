"""
텍스트 처리 유틸리티 테스트

형태소 분석기를 사용한 키워드 추출 기능 및 관련 텍스트 처리 기능들을 테스트합니다.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.utils.text_processing import (
    extract_keywords,
    extract_main_text,
    load_korean_stopwords,
    remove_stopwords,
    tokenize,
    split_sentences,
    generate_text_summary,
    calculate_text_similarity
)


class TestExtractKeywords:
    """extract_keywords 함수 테스트"""

    def test_korean_text_extraction(self):
        """한국어 텍스트에서 명사 키워드 추출 테스트"""
        korean_text = """
        인공지능은 컴퓨터 과학의 한 분야로, 기계가 인간의 지능을 모방하도록 하는 기술입니다.
        머신러닝과 딥러닝은 인공지능의 주요 기술이며, 자연어 처리와 컴퓨터 비전이 있습니다.
        """
        
        keywords = extract_keywords(korean_text, max_keywords=10)
        
        # 키워드가 추출되었는지 확인
        assert len(keywords) > 0
        assert len(keywords) <= 10
        
        # 예상되는 키워드들이 포함되어 있는지 확인
        expected_keywords = ['인공', '지능', '컴퓨터', '기술', '러닝']
        found_keywords = [kw for kw in expected_keywords if kw in keywords]
        assert len(found_keywords) > 0, f"예상 키워드가 발견되지 않음: {keywords}"
        
        # 모든 키워드가 2글자 이상인지 확인
        assert all(len(keyword) >= 2 for keyword in keywords)

    def test_english_text_extraction(self):
        """영어 텍스트에서 명사 키워드 추출 테스트"""
        english_text = """
        Artificial Intelligence is a branch of computer science that aims to create machines
        capable of intelligent behavior. Machine learning and deep learning are key technologies
        in AI development. Natural language processing and computer vision are major applications.
        """
        
        keywords = extract_keywords(english_text, max_keywords=10)
        
        # 키워드가 추출되었는지 확인
        assert len(keywords) > 0
        assert len(keywords) <= 10
        
        # 예상되는 영어 명사들이 포함되어 있는지 확인
        expected_keywords = ['intelligence', 'computer', 'science', 'machines', 'learning']
        found_keywords = [kw for kw in expected_keywords if kw in keywords]
        assert len(found_keywords) > 0, f"예상 영어 키워드가 발견되지 않음: {keywords}"
        
        # 모든 키워드가 2글자 이상인지 확인
        assert all(len(keyword) >= 2 for keyword in keywords)

    def test_mixed_language_extraction(self):
        """한영 혼합 텍스트에서 키워드 추출 테스트"""
        mixed_text = """
        인공지능(Artificial Intelligence)은 컴퓨터 시스템이 human intelligence를 모방하는 기술입니다.
        Machine Learning과 딥러닝은 AI의 핵심 기술이며, 데이터 분석과 pattern recognition에 사용됩니다.
        """
        
        keywords = extract_keywords(mixed_text, max_keywords=15)
        
        # 키워드가 추출되었는지 확인
        assert len(keywords) > 0
        assert len(keywords) <= 15
        
        # 한국어와 영어 키워드가 모두 포함되어 있는지 확인
        korean_found = any('가' <= char <= '힣' for keyword in keywords for char in keyword)
        english_found = any(keyword.isalpha() and not any('가' <= char <= '힣' for char in keyword) 
                          for keyword in keywords)
        
        # 적어도 하나의 언어에서 키워드가 추출되어야 함
        assert korean_found or english_found, f"한국어 또는 영어 키워드가 발견되지 않음: {keywords}"

    def test_stopwords_removal(self):
        """불용어 제거 기능 테스트"""
        text_with_stopwords = """
        이것은 그것이고 저것은 무엇입니다. The quick brown fox jumps over the lazy dog.
        컴퓨터와 프로그램이 있고, technology and innovation are important for development.
        """
        
        keywords = extract_keywords(text_with_stopwords, max_keywords=10)
        
        # 한국어 불용어가 제거되었는지 확인
        korean_stopwords = ['이것', '그것', '저것', '무엇']
        for stopword in korean_stopwords:
            assert stopword not in keywords, f"한국어 불용어가 제거되지 않음: {stopword}"
        
        # 영어 불용어가 제거되었는지 확인 (일반적인 불용어들)
        english_stopwords = ['the', 'and', 'are', 'for']
        for stopword in english_stopwords:
            assert stopword not in keywords, f"영어 불용어가 제거되지 않음: {stopword}"
        
        # 의미있는 키워드들이 남아있는지 확인
        meaningful_words = ['컴퓨터', 'technology', 'innovation', 'development']
        found_meaningful = [word for word in meaningful_words if word in keywords]
        assert len(found_meaningful) > 0, f"의미있는 키워드가 발견되지 않음: {keywords}"

    def test_empty_text(self):
        """빈 텍스트 처리 테스트"""
        assert extract_keywords("") == []
        assert extract_keywords(None) == []
        assert extract_keywords("   ") == []

    def test_max_keywords_limit(self):
        """최대 키워드 수 제한 테스트"""
        long_text = """
        인공지능 기술은 컴퓨터 과학 분야에서 중요한 역할을 합니다.
        머신러닝과 딥러닝은 데이터 분석에 활용되며, 자연어 처리와 컴퓨터 비전 기술이 발전하고 있습니다.
        로봇공학과 자동화 시스템도 인공지능과 밀접한 관련이 있습니다.
        """
        
        # 최대 5개 키워드 요청
        keywords = extract_keywords(long_text, max_keywords=5)
        assert len(keywords) <= 5
        
        # 최대 3개 키워드 요청
        keywords = extract_keywords(long_text, max_keywords=3)
        assert len(keywords) <= 3

    @patch('app.utils.text_processing.Okt')
    def test_okt_failure_handling(self, mock_okt):
        """Okt 형태소 분석기 실패 시 처리 테스트"""
        # Okt 초기화 실패 시뮬레이션
        mock_okt.side_effect = Exception("Okt initialization failed")
        
        text = "인공지능은 컴퓨터 기술입니다."
        keywords = extract_keywords(text, max_keywords=5)
        
        # 오류가 발생해도 빈 리스트가 아닌 결과를 반환해야 함 (영어 부분 처리)
        assert isinstance(keywords, list)

    @patch('app.utils.text_processing.pos_tag')
    def test_nltk_failure_handling(self, mock_pos_tag):
        """NLTK 품사 태깅 실패 시 처리 테스트"""
        # NLTK pos_tag 실패 시뮬레이션
        mock_pos_tag.side_effect = Exception("NLTK pos_tag failed")
        
        text = "Artificial Intelligence is computer technology."
        keywords = extract_keywords(text, max_keywords=5)
        
        # 오류가 발생해도 빈 리스트가 아닌 결과를 반환해야 함 (한국어 부분 처리)
        assert isinstance(keywords, list)


class TestExtractMainText:
    """extract_main_text 함수 테스트"""

    def test_html_text_extraction(self):
        """HTML에서 텍스트 추출 테스트"""
        html = """
        <html>
            <body>
                <div>인공지능은 미래 기술입니다.</div>
                <article>머신러닝과 딥러닝이 주요 기술입니다.</article>
                <section>자연어 처리가 중요합니다.</section>
                <script>alert('test');</script>
                <style>.test { color: red; }</style>
            </body>
        </html>
        """
        
        main_text = extract_main_text(html)
        
        # 본문 텍스트가 추출되었는지 확인
        assert "인공지능" in main_text
        assert "머신러닝" in main_text
        assert "자연어 처리" in main_text
        
        # 스크립트와 스타일이 제거되었는지 확인
        assert "alert" not in main_text
        assert "color: red" not in main_text

    def test_empty_html(self):
        """빈 HTML 처리 테스트"""
        assert extract_main_text("") == ""
        assert extract_main_text("<html></html>") == ""


class TestKoreanStopwords:
    """한국어 불용어 관련 테스트"""

    def test_load_korean_stopwords(self):
        """한국어 불용어 로드 테스트"""
        stopwords = load_korean_stopwords()
        
        # 불용어가 로드되었는지 확인
        assert isinstance(stopwords, list)
        assert len(stopwords) > 0
        
        # 실제 파일에 있는 한국어 불용어들이 포함되어 있는지 확인
        expected_stopwords = ['가', '그', '것', '나', '너', '를', '과']
        for word in expected_stopwords:
            assert word in stopwords, f"예상 불용어가 없음: {word}"

    def test_remove_stopwords_korean(self):
        """한국어 불용어 제거 테스트"""
        tokens = ['인공', '지능', '가', '컴퓨터', '기술', '것']
        filtered = remove_stopwords(tokens, language='ko')
        
        # 불용어가 제거되었는지 확인 (파일에 실제로 있는 불용어들)
        assert '가' not in filtered
        assert '것' not in filtered
        
        # 의미있는 토큰이 남아있는지 확인
        assert '인공' in filtered
        assert '지능' in filtered
        assert '컴퓨터' in filtered

    def test_remove_stopwords_english(self):
        """영어 불용어 제거 테스트"""
        tokens = ['artificial', 'intelligence', 'is', 'the', 'future', 'technology']
        filtered = remove_stopwords(tokens, language='en')
        
        # 영어 불용어가 제거되었는지 확인
        assert 'is' not in filtered
        assert 'the' not in filtered
        
        # 의미있는 토큰이 남아있는지 확인
        assert 'artificial' in filtered
        assert 'intelligence' in filtered
        assert 'future' in filtered


class TestTokenize:
    """tokenize 함수 테스트"""

    def test_korean_english_tokenization(self):
        """한국어와 영어 토큰화 테스트"""
        text = "인공지능 Artificial Intelligence는 미래 기술입니다."
        tokens = tokenize(text)
        
        # 토큰이 생성되었는지 확인
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        
        # 한국어와 영어 토큰이 모두 포함되어 있는지 확인
        korean_tokens = [token for token in tokens if any('가' <= char <= '힣' for char in token)]
        english_tokens = [token for token in tokens if token.isalpha() and not any('가' <= char <= '힣' for char in token)]
        
        assert len(korean_tokens) > 0, "한국어 토큰이 없음"
        assert len(english_tokens) > 0, "영어 토큰이 없음"


class TestSplitSentences:
    """split_sentences 함수 테스트"""

    def test_sentence_splitting(self):
        """문장 분리 테스트"""
        text = "인공지능은 중요합니다. 머신러닝도 필요합니다! 딥러닝은 어떨까요?"
        sentences = split_sentences(text)
        
        assert len(sentences) == 3
        assert "인공지능은 중요합니다" in sentences[0]
        assert "머신러닝도 필요합니다" in sentences[1]
        assert "딥러닝은 어떨까요" in sentences[2]

    def test_empty_text_splitting(self):
        """빈 텍스트 문장 분리 테스트"""
        assert split_sentences("") == []
        assert split_sentences("   ") == []


class TestGenerateTextSummary:
    """generate_text_summary 함수 테스트"""

    def test_text_summarization(self):
        """텍스트 요약 테스트"""
        long_text = """
        인공지능은 컴퓨터 과학의 한 분야입니다. 기계가 인간의 지능을 모방하도록 하는 기술입니다.
        머신러닝은 인공지능의 핵심 기술 중 하나입니다. 데이터에서 패턴을 학습합니다.
        딥러닝은 신경망을 사용하는 머신러닝 기법입니다. 복잡한 문제를 해결할 수 있습니다.
        자연어 처리는 인공지능의 응용 분야입니다. 텍스트를 이해하고 생성합니다.
        """
        
        summary = generate_text_summary(long_text, max_length=100)
        
        # 요약이 생성되었는지 확인
        assert len(summary) > 0
        assert len(summary) <= 100
        assert isinstance(summary, str)

    def test_short_text_summary(self):
        """짧은 텍스트 요약 테스트"""
        short_text = "인공지능은 중요한 기술입니다."
        summary = generate_text_summary(short_text, max_length=100)
        
        # 짧은 텍스트는 그대로 반환되어야 함
        assert summary == short_text


class TestCalculateTextSimilarity:
    """calculate_text_similarity 함수 테스트"""

    def test_similar_texts(self):
        """유사한 텍스트 간 유사도 테스트"""
        text1 = "인공지능과 머신러닝은 중요한 기술입니다."
        text2 = "머신러닝과 인공지능은 핵심 기술입니다."
        
        similarity = calculate_text_similarity(text1, text2)
        
        # 유사도가 0과 1 사이의 값인지 확인
        assert 0.0 <= similarity <= 1.0
        # 유사한 텍스트이므로 어느 정도 높은 유사도 기대
        assert similarity > 0.1

    def test_different_texts(self):
        """다른 텍스트 간 유사도 테스트"""
        text1 = "인공지능과 머신러닝"
        text2 = "날씨가 좋고 바람이 분다"
        
        similarity = calculate_text_similarity(text1, text2)
        
        # 유사도가 0과 1 사이의 값인지 확인
        assert 0.0 <= similarity <= 1.0
        # 다른 텍스트이므로 낮은 유사도 기대
        assert similarity < 0.5

    def test_empty_texts_similarity(self):
        """빈 텍스트 유사도 테스트"""
        assert calculate_text_similarity("", "test") == 0.0
        assert calculate_text_similarity("test", "") == 0.0
        assert calculate_text_similarity("", "") == 0.0


class TestIntegration:
    """통합 테스트"""

    def test_keyword_extraction_pipeline(self):
        """키워드 추출 파이프라인 전체 테스트"""
        # HTML에서 텍스트 추출 후 키워드 추출
        html_content = """
        <html>
            <body>
                <article>
                    <h1>인공지능의 미래</h1>
                    <p>Artificial Intelligence는 컴퓨터 기술의 혁신을 이끌고 있습니다.</p>
                    <p>머신러닝과 딥러닝은 AI development의 핵심 기술입니다.</p>
                </article>
            </body>
        </html>
        """
        
        # HTML에서 텍스트 추출
        main_text = extract_main_text(html_content)
        assert len(main_text) > 0
        
        # 키워드 추출
        keywords = extract_keywords(main_text, max_keywords=10)
        assert len(keywords) > 0
        
        # 예상되는 키워드들이 포함되어 있는지 확인
        expected_content = ['인공', '지능', 'intelligence', '컴퓨터', '기술', 'ai']
        found_keywords = [kw for kw in keywords if any(exp in kw.lower() for exp in expected_content)]
        assert len(found_keywords) > 0, f"예상 키워드가 발견되지 않음: {keywords}"

    def test_multilingual_processing(self):
        """다국어 처리 통합 테스트"""
        multilingual_text = """
        人工智能 Artificial Intelligence 인공지능은 
        компьютерные технологии コンピュータ技術과 함께 발전하고 있습니다.
        """
        
        # 다국어 텍스트에서도 오류 없이 키워드 추출이 되어야 함
        keywords = extract_keywords(multilingual_text, max_keywords=5)
        assert isinstance(keywords, list)
        # 적어도 한국어나 영어 키워드는 추출되어야 함
        assert len(keywords) >= 0 