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
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from konlpy.tag import Okt
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

from app.core.config import settings

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



def extract_keywords_tfidf(user_id: int, text: str, s3_key:str, top_n=3) -> list:
    """
    문서에서 TF-IDF 기반 키워드를 추출합니다.
    
    1. RecursiveCharacterTextSplitter로 문서를 분할합니다.
    2. 사용자의 ChromaDB 키워드 정보를 반영하여 가중치를 적용합니다.
    3. 상위 키워드를 반환합니다.
    
    빈 입력이나 에러 발생 시 빈 리스트를 반환합니다.

    Args:
        user_id (int): 사용자 ID
        text (str): 분석할 텍스트
        s3_key (str): S3에서 다운로드한 HTML 콘텐츠의 키
        top_n (int): 반환할 상위 키워드 개수
    Returns:
        list: 추출된 키워드 리스트
    """
    # 1) 빈 입력 예외 처리
    if not text or not text.strip():
        print("입력 텍스트가 비어있습니다.")
        print(f"s3_key: {s3_key}")
        return []

    collection = Chroma(
        persist_directory=settings.CHROMA_DB_URI,
        embedding_function=embeddings,
        collection_name="nebula_html",
    )

    # 2) 사용자 기존 키워드/가중치 조회
    user_data = collection.get(
        where={"user_id": user_id},
        include=["documents", "metadatas"]
    )
    user_keywords = user_data.get("documents", [])
    user_keyword_weights = {
        meta["keyword"]: meta["weight"]
        for meta in user_data.get("metadatas", [])
    }

    # 3) 문서 분할
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_text(text)

    # 4) 토큰이 전혀 없거나 모두 공백인 청크만 있을 때 예외 처리
    if not any(chunk.strip() for chunk in chunks):
        print("모든 청크가 비어있습니다.")
        print(f"s3_key: {s3_key}")
        return []

    # 5) TF-IDF 벡터화 및 예외 처리
    vectorizer = TfidfVectorizer(
        tokenizer=tokenize,
        token_pattern=None,
        ngram_range=(1, 2)
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(chunks)
    except ValueError as e:
        # sklearn 에러 메시지가 "empty vocabulary" 일 경우 빈 리스트 반환
        if "empty vocabulary" in str(e):
            print("어휘가 비어있습니다.")
            print(f"s3_key: {s3_key}")
            return []
        else:
            # 예측하지 못한 에러는 다시 발생시켜 상위 로직에서 처리하게 함
            raise

    # 6) 각 토큰에 대한 평균 스코어 계산
    scores = np.mean(tfidf_matrix.toarray(), axis=0)
    features = vectorizer.get_feature_names_out()
    extracted = list(zip(features, scores))

    # 7) 사용자 가중치 반영
    weighted = []
    for word, score in extracted:
        weight = user_keyword_weights.get(word, 1.0)
        if word in user_keywords:
            weight *= 1.5
        weighted.append((word, score * weight))

    # 8) 정렬 후 상위 N개 반환
    weighted.sort(key=lambda x: x[1], reverse=True)
    return [word for word, _ in weighted[:top_n]]
