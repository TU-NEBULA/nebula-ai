import re
import numpy as np
from bs4 import BeautifulSoup
from sklearn.metrics.pairwise import cosine_similarity
from app.core.embedding_model import get_embedding



def extract_main_text(html: str) -> str:
    """
    BeautifulSoup으로 HTML을 파싱하여 본문 텍스트를 최대한 깔끔하게 추출.
    여기서는 <div>, <article>, <section> 태그 기준으로 텍스트를 모음.
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # 본문 내용을 포함할 가능성이 높은 태그들
    # print(soup.text)
    content_tags = soup.find_all(['div', 'article', 'section'])
    texts = []
    
    for tag in content_tags:
        text = tag.get_text(strip=True)
        if text:
            texts.append(text)
    
    main_text = "\n".join(texts)
    main_text = re.sub(r'\s+', ' ', main_text).strip()
    return main_text


def split_sentences(text: str) -> list:
    """
    간단히 정규식으로 마침표, 느낌표, 물음표 뒤에서 분리.
    """
    # (?<=[.!?]) 뒤에 공백 또는 문장 끝이 오면 분리
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences

