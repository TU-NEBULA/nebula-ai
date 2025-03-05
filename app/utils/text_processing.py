import re
import os
import numpy as np
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from konlpy.tag import Okt
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords


def extract_main_text(html: str) -> str:
    """
    BeautifulSoup으로 HTML을 파싱하여 본문 텍스트를 최대한 깔끔하게 추출.
    <div>, <article>, <section> 태그 기준으로 텍스트를 모음.
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
    간단히 정규식으로 마침표, 느낌표, 물음표 뒤에서 분리.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def tokenize(text):
    okt = Okt()
    korean_tokens = okt.nouns(text)

    english_text = text.lower()
    english_tokens = word_tokenize(english_text)

    korean_tokens = remove_stopwords(korean_tokens, language='ko')
    english_tokens = remove_stopwords(english_tokens, language='en')
    
    return korean_tokens + english_tokens


def load_korean_stopwords(file_name='ko_stopwords.txt', tokenizer=None):
    """
    한국어 불용어 리스트를 파일에서 불러오는 함수.
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


def remove_stopwords(tokens, language='en'):
    if language == 'en':
        stop_words = set(stopwords.words('english'))
    else:
        stop_words = set(load_korean_stopwords())
    return [token for token in tokens if token not in stop_words]


def extract_keywords_tfidf(text, top_n=3) -> list:
    vectorizer = TfidfVectorizer(
        tokenizer=tokenize, 
        token_pattern=None,
        ngram_range=(1, 2)
    )
    tfidf_matrix = vectorizer.fit_transform([text])
    scores = tfidf_matrix.toarray()[0]

    keywords = [(word, score) for word, score in zip(vectorizer.get_feature_names_out(), scores)]
    keywords = sorted(keywords, key=lambda x: x[1], reverse=True)
    
    return [word for word, score in keywords[:top_n]]
