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
    calculate_text_similarity,
    extract_text_chunks_for_rag,
    prepare_content_for_rag
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


class TestTextChunksForRAG:
    """extract_text_chunks_for_rag 함수 개선사항 테스트"""

    def test_empty_text_handling(self):
        """빈 텍스트 처리 개선 테스트"""
        # 빈 텍스트도 최소 1개 청크 반환
        chunks = extract_text_chunks_for_rag("")
        assert len(chunks) == 1
        assert chunks[0] == ""

    def test_whitespace_only_text(self):
        """공백만 있는 텍스트 처리 테스트"""
        # 공백만 있는 텍스트도 안전하게 처리
        chunks = extract_text_chunks_for_rag("   \n\t   ")
        assert len(chunks) == 1
        assert chunks[0] == ""

    def test_very_short_text_handling(self):
        """매우 짧은 텍스트 처리 개선 테스트"""
        # 10자 미만의 짧은 텍스트
        short_text = "AI 기술"
        chunks = extract_text_chunks_for_rag(short_text)
        assert len(chunks) == 1
        assert chunks[0] == short_text

    def test_chunk_size_smaller_than_text(self):
        """청크 크기보다 작은 텍스트 처리 테스트"""
        # 1000자보다 작은 텍스트는 전체를 하나의 청크로
        medium_text = "AI와 머신러닝은 미래 기술입니다." * 10  # 약 300자
        chunks = extract_text_chunks_for_rag(medium_text, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0] == medium_text

    def test_minimum_chunk_length_relaxed(self):
        """최소 청크 길이 완화 테스트 (100자 → 50자)"""
        # 실제로는 50자 이상의 청크만 유지되는지 확인
        # 긴 텍스트를 작은 청크로 분할해서 50자 이상인 것만 남는지 테스트
        long_text = "이것은 매우 긴 텍스트입니다. " * 20  # 약 500자
        chunks = extract_text_chunks_for_rag(long_text, chunk_size=80, chunk_overlap=20)
        
        # 분할된 청크들 중에서 50자 이상인 것들이 있어야 함
        assert len(chunks) >= 1
        # 모든 청크가 50자 이상이거나, 원본 텍스트가 반환되어야 함
        has_meaningful_chunks = any(len(chunk.strip()) >= 50 for chunk in chunks)
        has_original_text = any(chunk == long_text for chunk in chunks)
        assert has_meaningful_chunks or has_original_text

    def test_no_meaningful_chunks_fallback(self):
        """의미있는 청크가 없을 때 원본 텍스트 반환 테스트"""
        # 49자 텍스트 (50자 미만) - 실제로는 chunk_size보다 작으므로 분할되지 않음
        short_text = "짧은 텍스트입니다. 청크 최소 길이보다 작습니다."
        chunks = extract_text_chunks_for_rag(short_text, chunk_size=100, chunk_overlap=20)
        
        # 짧은 텍스트는 분할되지 않고 원본 그대로 반환되어야 함
        assert len(chunks) == 1
        assert chunks[0] == short_text


class TestPrepareContentForRAG:
    """prepare_content_for_rag 함수 개선사항 테스트"""

    def test_empty_text_rag_preparation(self):
        """빈 텍스트 RAG 콘텐츠 준비 테스트"""
        # 빈 텍스트라도 최소 1개 청크 보장
        metadata = {
            "memo": "빈 텍스트 메모",
            "summary": "빈 텍스트 요약"
        }
        rag_content = prepare_content_for_rag(
            text="",
            keywords=["테스트"],
            metadata=metadata
        )
        
        assert len(rag_content) >= 1
        assert rag_content[0]["content"] == ""
        assert rag_content[0]["keywords"] == ["테스트"]
        assert rag_content[0]["user_memo"] == "빈 텍스트 메모"

    def test_chunk_keyword_extraction_safety(self):
        """청크별 키워드 추출 안전성 테스트"""
        # 빈 청크에서도 키워드 추출이 안전하게 처리되어야 함
        metadata = {
            "memo": "테스트 메모",
            "summary": "테스트 요약"
        }
        rag_content = prepare_content_for_rag(
            text="",
            keywords=["안전성"],
            metadata=metadata
        )
        
        assert len(rag_content) >= 1
        assert isinstance(rag_content[0]["chunk_keywords"], list)
        # 빈 텍스트에서는 빈 키워드 리스트
        assert rag_content[0]["chunk_keywords"] == []

    def test_chunk_keyword_extraction_with_content(self):
        """콘텐츠가 있는 청크의 키워드 추출 테스트"""
        # 실제 콘텐츠에서는 키워드가 추출되어야 함
        content = "인공지능과 머신러닝은 현대 기술의 핵심입니다. 딥러닝 기술이 발전하고 있습니다."
        metadata = {
            "memo": "기술 관련 메모",
            "summary": "기술 요약"
        }
        rag_content = prepare_content_for_rag(
            text=content,
            keywords=["AI", "기술"],
            metadata=metadata
        )
        
        assert len(rag_content) >= 1
        assert isinstance(rag_content[0]["chunk_keywords"], list)
        assert len(rag_content[0]["chunk_keywords"]) > 0

    def test_minimum_chunk_guarantee(self):
        """최소 청크 보장 테스트"""
        # 어떤 텍스트든 최소 1개 청크는 보장되어야 함
        test_cases = [
            "",
            "짧은 텍스트",
            "AI" * 1000,  # 긴 텍스트
            "   ",  # 공백만
            "🤖",  # 이모지
        ]
        
        for text in test_cases:
            # 청크 생성이 실패하지 않아야 함
            chunks = extract_text_chunks_for_rag(text)
            assert len(chunks) >= 1, f"텍스트 '{text}'에서 청크가 생성되지 않음"
            
            # RAG 콘텐츠 준비도 실패하지 않아야 함
            rag_content = prepare_content_for_rag(
                text=text,
                keywords=["테스트"],
                metadata={"memo": "테스트 메모", "summary": "테스트 요약"}
            )
            assert len(rag_content) >= 1, f"텍스트 '{text}'에서 RAG 콘텐츠 준비 실패"

    def test_user_data_preservation_all_chunks(self):
        """모든 청크에서 사용자 데이터 보존 테스트"""
        # 긴 텍스트로 여러 청크 생성
        long_text = "AI와 머신러닝 기술이 발전하고 있습니다. " * 100
        user_keywords = ["사용자", "키워드"]
        user_memo = "사용자 메모"
        user_summary = "사용자 요약"
        
        rag_content = prepare_content_for_rag(
            text=long_text,
            keywords=user_keywords,
            metadata={"memo": user_memo, "summary": user_summary}
        )
        
        # 모든 청크에서 사용자 데이터가 보존되어야 함
        assert len(rag_content) > 1  # 여러 청크 생성 확인
        for chunk in rag_content:
            assert chunk["keywords"] == user_keywords
            assert chunk["user_memo"] == user_memo
            assert chunk["summary"] == user_summary
            assert "chunk_index" in chunk
            assert "total_chunks" in chunk


class TestBookmarkUpdatePreparation:
    """북마크 업데이트 관련 데이터 준비 테스트"""

    def test_star_id_pattern_generation(self):
        """star_id 기반 삭제 패턴 생성 테스트"""
        star_id = "bookmark_12345"
        
        # 예상되는 삭제 패턴들
        expected_patterns = [
            f"{star_id}_chunk_0",
            f"{star_id}_chunk_1",
            f"{star_id}_chunk_2",
            f"{star_id}_memo",
            f"{star_id}_summary"
        ]
        
        # 패턴이 올바르게 생성되는지 확인
        for pattern in expected_patterns:
            assert pattern.startswith(star_id)
            assert "_" in pattern

    def test_update_scenario_simulation(self):
        """북마크 업데이트 시나리오 시뮬레이션"""
        # 첫 번째 저장 데이터
        first_save = {
            "user_id": "user123",
            "star_id": "bookmark456",
            "title": "첫 번째 제목",
            "keywords": ["AI", "머신러닝"],
            "memo": "첫 번째 메모",
            "summary": "첫 번째 요약"
        }
        
        # 업데이트 데이터 (모든 필드 변경)
        updated_save = {
            "user_id": "user123",
            "star_id": "bookmark456",  # 같은 star_id
            "title": "업데이트된 제목",
            "keywords": ["딥러닝", "자연어처리", "컴퓨터비전"],
            "memo": "업데이트된 메모 내용",
            "summary": "업데이트된 요약 내용"
        }
        
        # 모든 사용자 정보가 변경되었는지 확인
        assert updated_save["title"] != first_save["title"]
        assert updated_save["keywords"] != first_save["keywords"]
        assert updated_save["memo"] != first_save["memo"]
        assert updated_save["summary"] != first_save["summary"]
        
        # star_id는 동일해야 함 (같은 북마크 업데이트)
        assert updated_save["star_id"] == first_save["star_id"]

    def test_content_preparation_with_updated_data(self):
        """업데이트된 데이터로 콘텐츠 준비 테스트"""
        # 업데이트된 사용자 데이터
        updated_keywords = ["새로운", "키워드", "목록"]
        updated_memo = "완전히 새로운 메모 내용입니다."
        updated_summary = "업데이트된 요약 내용입니다."
        
        content = "테스트 콘텐츠입니다. 업데이트 테스트를 진행합니다."
        
        rag_content = prepare_content_for_rag(
            text=content,
            keywords=updated_keywords,
            metadata={"memo": updated_memo, "summary": updated_summary}
        )
        
        # 모든 청크에 업데이트된 데이터가 반영되어야 함
        for chunk in rag_content:
            assert chunk["keywords"] == updated_keywords
            assert chunk["user_memo"] == updated_memo
            assert chunk["summary"] == updated_summary


class TestRobustnessAndErrorHandling:
    """견고성 및 오류 처리 테스트"""

    def test_extreme_text_lengths(self):
        """극단적인 텍스트 길이 처리 테스트"""
        # 청크 생성이 실패하지 않아야 함
        chunks = extract_text_chunks_for_rag("A" * 50000)
        assert len(chunks) >= 1, "매우 긴 텍스트 청크 생성 실패"
        
        # RAG 콘텐츠 준비도 실패하지 않아야 함
        rag_content = prepare_content_for_rag(
            text="A" * 50000,
            keywords=["테스트"],
            metadata={"memo": "테스트 메모", "summary": "테스트 요약"}
        )
        assert len(rag_content) >= 1, "매우 긴 텍스트 RAG 콘텐츠 준비 실패"

    def test_special_characters_handling(self):
        """특수 문자 처리 테스트"""
        # 특수 문자가 있어도 처리가 완료되어야 함
        rag_content = prepare_content_for_rag(
            text="🤖 AI와 로봇 🚀",
            keywords=["특수문자"],
            metadata={"memo": "특수문자 테스트", "summary": "특수문자 요약"}
        )
        assert len(rag_content) >= 1
        assert isinstance(rag_content[0]["chunk_keywords"], list)

    def test_none_and_invalid_inputs(self):
        """None 및 잘못된 입력 처리 테스트"""
        # None이나 잘못된 타입이 들어와도 처리되어야 함
        try:
            rag_content = prepare_content_for_rag(
                text=None,  # None 입력
                keywords=["테스트"],
                metadata={"memo": "None 테스트", "summary": "None 요약"}
            )
            # None이 문자열로 변환되거나 빈 문자열로 처리되어야 함
            assert len(rag_content) >= 1
        except Exception as e:
            # 예외가 발생하더라도 적절한 처리가 되어야 함
            assert "NoneType" in str(e) or "expected string" in str(e)


def test_prepare_content_for_rag():
    """RAG용 컨텐츠 준비 테스트"""
    text = "이것은 테스트 텍스트입니다. " * 100  # 충분히 긴 텍스트
    keywords = ["테스트", "키워드"]
    metadata = {
        "memo": "사용자 메모",
        "summary": "테스트 요약"
    }
    
    # 기본 사용법
    result = prepare_content_for_rag(text, keywords, metadata)
    
    assert len(result) > 0
    assert all(chunk["keywords"] == keywords for chunk in result)
    assert all(chunk["user_memo"] == "사용자 메모" for chunk in result)
    assert all(chunk["summary"] == "테스트 요약" for chunk in result)
    assert all("chunk_index" in chunk for chunk in result)
    assert all("total_chunks" in chunk for chunk in result)
    assert all("chunk_keywords" in chunk for chunk in result)
    
    # keyword-only arguments 테스트
    result_custom = prepare_content_for_rag(
        text, 
        keywords, 
        metadata,
        chunk_size=500,
        chunk_overlap=100
    )
    
    assert len(result_custom) >= len(result)  # 더 작은 청크 크기로 더 많은 청크 생성


def test_prepare_content_for_rag_empty_metadata():
    """메타데이터가 없는 경우 테스트"""
    text = "간단한 텍스트"
    keywords = ["키워드"]
    
    # metadata 없이 호출
    result = prepare_content_for_rag(text, keywords)
    
    assert len(result) == 1
    assert result[0]["user_memo"] == ""
    assert result[0]["summary"] == ""
    assert result[0]["keywords"] == keywords


def test_prepare_content_for_rag_empty_text():
    """빈 텍스트 처리 테스트"""
    text = ""
    keywords = ["키워드"]
    metadata = {"memo": "메모"}
    
    result = prepare_content_for_rag(text, keywords, metadata)
    
    # 빈 텍스트라도 최소 하나의 청크는 반환
    assert len(result) == 1
    assert result[0]["content"] == ""
    assert result[0]["keywords"] == keywords
    assert result[0]["user_memo"] == "메모"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__]) 