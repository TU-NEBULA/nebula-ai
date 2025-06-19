"""
텍스트 처리 유틸리티 모듈

이 모듈은 HTML 콘텐츠에서 본문 텍스트를 추출하고, 문장을 분리하며,
한국어와 영어 토큰을 생성하는 기능을 제공합니다.
TF-IDF 기반으로 키워드를 추출하는 기능도 포함되어 있습니다.
"""
import os
import re
from collections import Counter, defaultdict
from typing import List, Dict, Any

from bs4 import BeautifulSoup
from konlpy.tag import Okt
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from nltk.corpus import stopwords
from nltk.tag import pos_tag
from nltk.tokenize import word_tokenize
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_async_session
from app.services.vector_service import vector_service

# OpenAI 임베딩 모델 초기화
embeddings = OpenAIEmbeddings(
    model=settings.OPENAI_EMBED_MODEL or "text-embedding-3-small"
)

def extract_main_text(html: str) -> str:
    """
    BeautifulSoup으로 HTML을 파싱하여 본문 텍스트를 최대한 깔끔하게 추출합니다.
    <div>, <article>, <section> 태그 기준으로 텍스트를 모아서 반환합니다.

    Args:
        html (str): HTML 콘텐츠
    Returns:
        str: 추출된 본문 텍스트
    """
    soup = BeautifulSoup(html, "html.parser")

    content_tags = soup.find_all(['div', 'article', 'section'])
    texts = []

    for tag in content_tags:
        text = tag.get_text(separator=" ", strip=True)
        if text:
            texts.append(text)

    main_text = "\n".join(texts)

    main_text = re.sub(r'[^\w\s]', '', main_text)
    main_text = re.sub(r'\s+', ' ', main_text).strip()

    return main_text


def split_sentences(text: str) -> list:
    """
    텍스트를 문장 단위로 분리합니다.
    정규식을 사용하여 마침표, 느낌표, 물음표 뒤에서 문장을 분리합니다.

    Args:
        text (str): 분석할 텍스트
    Returns:
        list: 분리된 문장 리스트
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def tokenize(text: str) -> list:
    """
    텍스트를 한국어와 영어 토큰으로 분리합니다.
    한국어는 Okt를 사용하여 명사를 추출하고, 영어는 NLTK word_tokenize를 사용합니다.
    두 언어 모두 불용어를 제거한 결과를 반환합니다.
    Args:
        text (str): 분석할 텍스트
    Returns:
        list: 한국어와 영어 토큰 리스트
    """
    okt = Okt()
    korean_tokens = okt.nouns(text)

    english_text = text.lower()
    english_tokens = word_tokenize(english_text)

    korean_tokens = remove_stopwords(korean_tokens, language='ko')
    english_tokens = remove_stopwords(english_tokens, language='en')

    return korean_tokens + english_tokens


def load_korean_stopwords(file_name: str = 'ko_stopwords.txt', tokenizer=None):
    """
    한국어 불용어 리스트를 파일에서 불러옵니다.
    선택적으로 토크나이저를 적용하여 불용어를 추가 처리할 수 있습니다.
    Args:
        file_name (str): 불용어 파일 이름
        tokenizer (callable): 선택적 토크나이저 함수
    Returns:
        list: 불용어 리스트
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, file_name)

    with open(file_path, 'r', encoding='utf-8') as f:
        stop_words = f.read().splitlines()

    if tokenizer is not None:
        processed = set()
        for sw in stop_words:
            tokens = tokenizer(sw)
            processed.update(tokens)
        return list(processed)

    return stop_words


def remove_stopwords(tokens: list, language: str = 'en'):
    """
    토큰 리스트에서 불용어를 제거합니다.
    언어(영어 또는 한국어)에 따라 적절한 불용어 세트를 적용합니다.

    Args:
        tokens (list): 토큰 리스트
        language (str): 언어 ('en' 또는 'ko')
    Returns:
        list: 불용어가 제거된 토큰 리스트
    """
    if language == 'en':
        stop_words = set(stopwords.words('english'))
    else:
        stop_words = set(load_korean_stopwords())
    return [token for token in tokens if token not in stop_words]


def extract_text_chunks_for_rag(text: str, chunk_size: int = 1000,
                                chunk_overlap: int = 200) -> List[str]:
    """
    RAG(Retrieval-Augmented Generation)용 텍스트 청크를 생성합니다.

    RAG의 경우 검색 성능을 위해 적절한 크기로 텍스트를 분할하는 것이 필수적입니다.
    각 청크는 독립적으로 검색 가능하면서도 충분한 맥락을 포함해야 합니다.

    짧은 텍스트의 경우에도 최소 하나의 청크는 반환하여 북마크 저장이 실패하지 않도록 합니다.

    Args:
        text (str): 분할할 텍스트
        chunk_size (int): 각 청크의 최대 크기 (기본값: 1000)
        chunk_overlap (int): 청크 간 겹치는 문자 수 (기본값: 200)

    Returns:
        List[str]: 분할된 텍스트 청크 리스트 (최소 1개 청크 보장)
    """
    if not text:
        return [""]  # 빈 텍스트라도 빈 청크 하나 반환

    text = text.strip()
    if not text:
        return [""]  # 공백만 있는 경우도 빈 청크 하나 반환

    # 텍스트가 chunk_size보다 작으면 전체를 하나의 청크로 반환
    if len(text) <= chunk_size:
        return [text]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks = splitter.split_text(text)

    # 청크가 없는 경우 원본 텍스트를 반환
    if not chunks:
        return [text]

    # 너무 짧은 청크는 제거하되, 모든 청크가 제거되면 원본 텍스트 반환
    # 100자에서 50자로 완화
    meaningful_chunks = [chunk.strip() for chunk in chunks
                        if len(chunk.strip()) >= 50]

    # 의미있는 청크가 없으면 원본 텍스트를 반환
    if not meaningful_chunks:
        return [text]

    return meaningful_chunks

def extract_text_chunks(text: str, chunk_size: int = 1000,
                       chunk_overlap: int = 200) -> List[str]:
    """
    일반적인 텍스트 분할 (기존 호환성 유지)

    기존 코드와의 호환성을 위해 유지하되, RAG용 분할을 위해서는
    extract_text_chunks_for_rag() 사용을 권장합니다.

    Args:
        text (str): 분할할 텍스트
        chunk_size (int): 각 청크의 최대 크기 (기본값: 1000)
        chunk_overlap (int): 청크 간 겹치는 문자 수 (기본값: 200)

    Returns:
        List[str]: 분할된 텍스트 청크 리스트
    """
    return extract_text_chunks_for_rag(text, chunk_size, chunk_overlap)

def extract_keywords(text: str, max_keywords: int = 20) -> List[str]:
    """
    텍스트에서 키워드를 추출합니다.

    키워드 추출의 경우 텍스트 분할하지 않고 전체 텍스트에서 TF-IDF를 계산하는 것이 더 효과적입니다.
    이는 문서 전체의 맥락을 고려하여 더 의미있는 키워드를 추출할 수 있기 때문입니다.

    이 함수는 다음과 같은 방법으로 키워드를 추출합니다:
    1. 형태소 분석을 통한 명사 추출 (한국어: Okt, 영어: NLTK pos_tag)
    2. 불용어 제거 (한국어: ko_stopwords.txt, 영어: NLTK stopwords)
    3. 빈도 분석
    4. 길이 기반 필터링
    5. 상위 키워드 선택

    Args:
        text (str): 키워드를 추출할 텍스트
        max_keywords (int): 최대 추출할 키워드 수 (기본값: 20)

    Returns:
        List[str]: 추출된 키워드 리스트
    """
    if not text:
        return []

    # 불용어 로드
    try:
        korean_stopwords = set(load_korean_stopwords())
    except (FileNotFoundError, UnicodeDecodeError):
        korean_stopwords = set()

    try:
        english_stopwords = set(stopwords.words('english'))
    except (ImportError, LookupError):
        english_stopwords = set()

    # 한국어 명사 추출
    korean_nouns = []
    try:
        okt = Okt()
        korean_nouns = okt.nouns(text)
        # 한국어 불용어 제거 및 길이 필터링
        korean_nouns = [
            noun for noun in korean_nouns
            if noun not in korean_stopwords and len(noun) >= 2
        ]
    except Exception:
        korean_nouns = []  # 명시적으로 빈 리스트 설정

    # 영어 명사 추출
    english_nouns = []
    try:
        # 영어 텍스트만 추출 (알파벳과 공백만)
        english_text = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
        english_text = re.sub(r'\s+', ' ', english_text).strip()

        if english_text:
            # 토큰화
            tokens = word_tokenize(english_text)

            # 빈 토큰 제거
            tokens = [token for token in tokens if token.strip()]

            if tokens:
                # 품사 태깅
                pos_tags = pos_tag(tokens)

                # 명사만 추출 (NN, NNS, NNP, NNPS)
                english_nouns = [
                    word for word, pos in pos_tags
                    if pos in ['NN', 'NNS', 'NNP', 'NNPS']
                    and word not in english_stopwords
                    and len(word) >= 2
                ]
    except Exception:
        english_nouns = []  # 명시적으로 빈 리스트 설정

    # 모든 명사 합치기
    all_nouns = korean_nouns + english_nouns

    if not all_nouns:
        return []

    # 빈도 계산
    noun_counts = Counter(all_nouns)

    # 상위 키워드 선택
    top_keywords = [word for word, _ in noun_counts.most_common(max_keywords)]

    return top_keywords

async def smart_keyword_extraction(
    text: str,
    user_id: str,
    max_keywords: int = 15,
    session: AsyncSession = None
) -> List[str]:
    """
    스마트 키워드 추출 함수

    이 함수는 다음과 같은 고급 기능을 제공합니다:
    1. 기본 키워드 추출
    2. 사용자의 PostgreSQL 벡터 데이터베이스 키워드 정보를 반영하여 가중치를 적용합니다.
    3. TF-IDF와 유사한 중요도 계산
    4. 컨텍스트 기반 키워드 선택

    Args:
        text (str): 키워드를 추출할 텍스트
        user_id (str): 사용자 ID (개인화된 키워드 추출을 위해)
        max_keywords (int): 최대 추출할 키워드 수 (기본값: 15)
        session (AsyncSession): 데이터베이스 세션

    Returns:
        List[str]: 스마트하게 추출된 키워드 리스트
    """
    if session is None:
        async for db_session in get_async_session():
            return await smart_keyword_extraction(text, user_id, max_keywords, db_session)

    # 1. 기본 키워드 추출
    basic_keywords = extract_keywords(text, max_keywords * 2)

    if not basic_keywords:
        return []

    # 2. 사용자의 기존 키워드 정보 가져오기 (PostgreSQL에서)
    try:
        # 사용자의 문서 통계 가져오기
        await vector_service.get_user_document_stats(session, user_id)

        # 사용자의 기존 문서에서 키워드 빈도 분석을 위한 간단한 검색
        # (실제로는 더 정교한 알고리즘이 필요할 수 있음)
        user_keyword_weights = defaultdict(float)

        # 기본 가중치 설정
        for keyword in basic_keywords:
            user_keyword_weights[keyword] = 1.0

        # 상위 키워드 선택
        weighted_keywords = sorted(
            user_keyword_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )

        final_keywords = [keyword for keyword, _ in weighted_keywords[:max_keywords]]

    except (ConnectionError, TimeoutError):
        # 오류 발생 시 기본 키워드 반환
        final_keywords = basic_keywords[:max_keywords]

    return final_keywords

def generate_text_summary(text: str, max_length: int = 200) -> str:
    """
    텍스트의 요약을 생성합니다.

    이 함수는 간단한 추출식 요약을 수행합니다:
    1. 문장별로 분할
    2. 길이와 위치를 고려한 점수 계산
    3. 상위 문장들을 조합하여 요약 생성

    Args:
        text (str): 요약할 텍스트
        max_length (int): 요약의 최대 길이 (기본값: 200)

    Returns:
        str: 생성된 요약
    """
    if not text or len(text) <= max_length:
        return text

    # 문장 분할 (간단한 방법)
    sentences = re.split(r'[.!?]\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return text[:max_length]

    # 각 문장의 점수 계산
    sentence_scores = []
    for i, sentence in enumerate(sentences):
        # 위치 점수 (앞쪽 문장일수록 높음)
        position_score = 1.0 - (i / len(sentences)) * 0.5

        # 길이 점수 (너무 짧거나 긴 문장은 낮음)
        length_score = min(len(sentence) / 100, 1.0) if len(sentence) > 20 else 0.5

        # 최종 점수
        total_score = position_score * length_score
        sentence_scores.append((i, sentence, total_score))

    # 점수 순으로 정렬
    sentence_scores.sort(key=lambda x: x[2], reverse=True)

    # 요약 생성
    summary_parts = []
    current_length = 0

    for i, sentence, _ in sentence_scores:
        if current_length + len(sentence) <= max_length:
            summary_parts.append((i, sentence))
            current_length += len(sentence)
        else:
            break

    # 원래 순서대로 정렬
    summary_parts.sort(key=lambda x: x[0])
    summary = ' '.join([sentence for i, sentence in summary_parts])

    # 길이 조절
    if len(summary) > max_length:
        summary = summary[:max_length-3] + '...'

    return summary

def calculate_text_similarity(text1: str, text2: str) -> float:
    """
    두 텍스트 간의 유사도를 계산합니다.

    이 함수는 간단한 코사인 유사도를 사용합니다:
    1. 각 텍스트에서 키워드 추출
    2. 키워드 벡터 생성
    3. 코사인 유사도 계산

    Args:
        text1 (str): 첫 번째 텍스트
        text2 (str): 두 번째 텍스트

    Returns:
        float: 0.0~1.0 사이의 유사도 점수
    """
    if not text1 or not text2:
        return 0.0

    # 각 텍스트에서 키워드 추출
    keywords1 = set(extract_keywords(text1))
    keywords2 = set(extract_keywords(text2))

    if not keywords1 or not keywords2:
        return 0.0

    # 교집합과 합집합 계산
    intersection = keywords1 & keywords2
    union = keywords1 | keywords2

    # Jaccard 유사도 계산
    jaccard_similarity = len(intersection) / len(union) if union else 0.0

    return jaccard_similarity

def extract_keywords_from_chunks(text: str, max_keywords: int = 20,
                                chunk_size: int = 2000) -> List[str]:
    """
    긴 텍스트의 경우 청크별로 키워드를 추출한 후 결합하는 방식

    매우 긴 텍스트(10,000자 이상)의 경우에만 사용을 권장합니다.
    일반적인 웹페이지 텍스트의 경우 extract_keywords()를 사용하는 것이 더 효과적입니다.

    Args:
        text (str): 키워드를 추출할 텍스트
        max_keywords (int): 최대 추출할 키워드 수 (기본값: 20)
        chunk_size (int): 청크 크기 (기본값: 2000, 키워드 추출용이므로 더 큰 사이즈)

    Returns:
        List[str]: 추출된 키워드 리스트
    """
    if not text or len(text) < 10000:
        # 짧은 텍스트는 일반 키워드 추출 사용
        return extract_keywords(text, max_keywords)

    # 긴 텍스트를 청크로 분할
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=400,  # 키워드 추출용이므로 더 많은 오버랩
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks = splitter.split_text(text)

    # 각 청크에서 키워드 추출
    all_keywords = []
    for chunk in chunks:
        chunk_keywords = extract_keywords(chunk, max_keywords=max_keywords * 2)
        all_keywords.extend(chunk_keywords)

    # 키워드 빈도 계산 및 상위 키워드 선택
    keyword_counts = Counter(all_keywords)
    top_keywords = [word for word, _ in keyword_counts.most_common(max_keywords)]

    return top_keywords

def prepare_content_for_rag(text: str, keywords: List[str],
                           metadata: Dict[str, str] = None, *,
                           chunk_size: int = 1000,
                           chunk_overlap: int = 200) -> List[Dict[str, Any]]:
    """
    RAG 챗봇을 위한 컨텐츠 준비

    사용자가 선택한 키워드와 메모를 포함하여 RAG에 최적화된 청크를 생성합니다.
    각 청크에는 원본 텍스트와 함께 메타데이터(키워드, 메모, 요약)가 포함됩니다.

    짧은 텍스트나 빈 텍스트의 경우에도 최소 하나의 청크를 반환하여
    북마크 저장이 실패하지 않도록 보장합니다.

    Args:
        text (str): 원본 텍스트
        keywords (List[str]): 사용자가 선택한 키워드
        metadata (Dict[str, str]): 메타데이터 (memo, summary 등)
        chunk_size (int): 청크 크기 (keyword-only)
        chunk_overlap (int): 청크 오버랩 (keyword-only)

    Returns:
        List[Dict[str, Any]]: RAG용 메타데이터가 포함된 청크 리스트 (최소 1개 보장)
    """
    if metadata is None:
        metadata = {}

    memo = metadata.get('memo', '')
    summary = metadata.get('summary', '')

    # 텍스트를 청크로 분할 (최소 1개 청크 보장)
    chunks = extract_text_chunks_for_rag(text, chunk_size, chunk_overlap)

    # 청크가 없는 경우 빈 청크라도 생성 (안전장치)
    if not chunks:
        chunks = [text or ""]

    # 각 청크에 메타데이터 추가
    enriched_chunks = []
    for i, chunk in enumerate(chunks):
        # 청크별 키워드 추출 (빈 청크의 경우 빈 리스트)
        try:
            chunk_keywords = (extract_keywords(chunk, max_keywords=10)
                            if chunk and chunk.strip() else [])
        except (ImportError, LookupError):
            chunk_keywords = []

        enriched_chunk = {
            "content": chunk,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "keywords": keywords,
            "user_memo": memo,
            "summary": summary,
            # 청크별 키워드 (해당 청크에서만 추출된 키워드)
            "chunk_keywords": chunk_keywords,
        }
        enriched_chunks.append(enriched_chunk)

    return enriched_chunks
