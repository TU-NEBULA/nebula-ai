"""
북마크 저장 태스크 모듈

이 모듈은 웹 페이지 북마크를 처리하고 벡터 데이터베이스에 저장하는 Celery 태스크를 정의합니다.
S3에서 HTML 콘텐츠를 가져오고, 텍스트를 추출하여 청크로 나눈 다음, 임베딩하여 ChromaDB에 저장합니다.
"""

from app.core.celery_worker import celery
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

from app.core.config import settings
from app.external.s3_service import download_html_from_s3

# OpenAI 임베딩 모델 초기화
embeddings = OpenAIEmbeddings(
    model=settings.OPENAI_EMBED_MODEL or "text-embedding-3-small"
)

# 텍스트 분할기 초기화 - 1000자 크기의 청크로 나누고 200자 겹침
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


def _save_bookmark_logic(user_id: int , star_id: str, s3_key: str, keywords:list, memo: str, summary: str) -> dict:
    """
    북마크를 벡터 데이터베이스에 저장하는 핵심 로직 함수

    이 함수는 S3에서 HTML 콘텐츠를 가져와 텍스트로 변환하고,
    텍스트를 청크로 나눈 다음 벡터 데이터베이스에 저장합니다.
    기존에 동일한 star_id로 저장된 항목이 있으면 먼저 삭제합니다.

    Args:
        user_id (int): 사용자 ID
        star_id (str): 북마크 ID
        s3_key (str): S3에 저장된 HTML 콘텐츠의 키
        keywords (list): 북마크와 관련된 키워드 목록
        memo (str): 사용자가 작성한 메모
        summary (str): 북마크 내용 요약

    Returns:
        dict: 저장 성공 여부 및 저장된 청크 수 정보
    """
    # S3에서 HTML 다운로드 및 텍스트 추출
    html = download_html_from_s3(s3_key)
    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(separator="\n")

    # 텍스트를 청크로 분할
    chunks = splitter.split_text(body_text)

    # ChromaDB 벡터스토어 초기화
    vectorstore = Chroma(
        persist_directory=settings.CHROMA_DB_URI,
        embedding_function=embeddings,
        collection_name="nebula_html",
    )

    # 기존 동일 북마크 데이터 삭제
    existing_ids = vectorstore._collection.get(include=["ids"])["ids"]
    to_delete = [i for i in existing_ids if i.startswith(f"{star_id}-")]
    if to_delete:
        vectorstore.delete(ids=to_delete)

    # 새 북마크 데이터용 ID 및 메타데이터 생성
    ids = [f"{star_id}-{i}" for i in range(len(chunks))]
    metadatas = [
        dict(
            user_id=user_id,
            s3_key=s3_key,
            keywords=keywords,
            memo=memo,
            summary=summary
        )
        for _ in chunks
    ]

    # 벡터스토어에 텍스트 청크 추가
    vectorstore.add_texts(
        texts=chunks,
        ids=ids,
        metadatas=metadatas,
        embedding=embeddings.embed_documents,
    )

    # 변경사항 저장
    vectorstore.persist()
    return {"status": "success", "inserted": len(chunks)}


@celery.task(
    name="tasks.save_bookmark",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_jitter=True,
)
def save_bookmark_task(self, user_id: int, star_id: str, s3_key: str, keywords:list, memo:str, summary:str) -> dict:
    """
    북마크를 벡터 데이터베이스에 저장하는 Celery 태스크

    이 태스크는 예외 발생 시 최대 3회까지 자동으로 재시도하며,
    재시도 간격은 지수적으로 증가하고 무작위 지터(jitter)가 추가됩니다.

    Args:
        self: Celery 태스크 인스턴스
        user_id (int): 사용자 ID
        star_id (str): 북마크 ID
        s3_key (str): S3에 저장된 HTML 콘텐츠의 키
        keywords (list): 북마크와 관련된 키워드 목록
        memo (str): 사용자가 작성한 메모
        summary (str): 북마크 내용 요약

    Returns:
        dict: 저장 성공 여부 및 저장된 청크 수 정보
    """
    return _save_bookmark_logic(user_id, star_id, s3_key, keywords, memo, summary)
