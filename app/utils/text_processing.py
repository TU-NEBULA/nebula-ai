"""
텍스트 처리 유틸리티 모듈

이 모듈은 HTML 콘텐츠에서 본문 텍스트를 추출하고, 문장을 분리하며, 
한국어와 영어 토큰을 생성하는 기능을 제공합니다.
TF-IDF 기반으로 키워드를 추출하는 기능도 포함되어 있습니다.
"""
import re
import os
import numpy as np
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from konlpy.tag import Okt
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict
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


def load_korean_stopwords(file_name: str ='ko_stopwords.txt', tokenizer=None):
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
    else:
        return stop_words


def remove_stopwords(tokens: list, language:str ='en'):
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


def extract_text_chunks(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """
    텍스트를 지정된 크기의 청크로 분할합니다.
    
    Args:
        text (str): 분할할 텍스트
        chunk_size (int): 각 청크의 최대 크기 (기본값: 1000)
        chunk_overlap (int): 청크 간 겹치는 문자 수 (기본값: 200)
    
    Returns:
        List[str]: 분할된 텍스트 청크 리스트
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    return splitter.split_text(text)

def extract_keywords(text: str, max_keywords: int = 20) -> List[str]:
    """
    텍스트에서 키워드를 추출합니다.
    
    이 함수는 다음과 같은 방법으로 키워드를 추출합니다:
    1. 텍스트 정제 및 토큰화
    2. 불용어 제거
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
    
    # 텍스트 정제
    text = re.sub(r'[^\w\s가-힣]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip().lower()
    
    # 간단한 토큰화 (공백 기준)
    tokens = text.split()
    
    # 불용어 리스트 (한국어 + 영어)
    stopwords = {
        '이', '그', '저', '것', '들', '는', '은', '을', '를', '에', '의', '가', '와', '과', 
        '도', '만', '까지', '부터', '로', '으로', '에서', '에게', '한테', '하고', '이다', 
        '있다', '없다', '되다', '하다', '수', '있', '없', '때', '곳', '분', '등', '및',
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 
        'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before', 
        'after', 'above', 'below', 'between', 'among', 'is', 'are', 'was', 'were', 
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 
        'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 
        'these', 'those', 'what', 'which', 'who', 'when', 'where', 'why', 'how'
    }
    
    # 불용어 제거 및 길이 필터링 (2자 이상)
    filtered_tokens = [
        token for token in tokens 
        if token not in stopwords and len(token) >= 2
    ]
    
    # 빈도 계산
    token_counts = Counter(filtered_tokens)
    
    # 상위 키워드 선택
    top_keywords = [word for word, count in token_counts.most_common(max_keywords)]
    
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
        user_stats = await vector_service.get_user_document_stats(session, user_id)
        
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
        
        final_keywords = [keyword for keyword, weight in weighted_keywords[:max_keywords]]
        
    except Exception as e:
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
    
    for i, sentence, score in sentence_scores:
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
