from app.core.celery_worker import celery
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

from app.core.config import settings
from app.external.s3_service import download_html_from_s3

embeddings = OpenAIEmbeddings(
    model=settings.OPENAI_EMBED_MODEL or "text-embedding-3-small"
)
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


# TODO
# 각 북마크간 유사도 계산을 위한 로직 필요
# - 새로 저장된 북마크를 기준으로
# - 해당 문서들을 임베딩하여 쿼리로 사용
# - 사용자 ID에 해당하는 북마크들 중에서 유사한 것들을 쿼리하여 결과를 반환
# - 모든 북마크 노드간 유사도를 계산해야하므로 알고리즘 설계 필요

def _save_bookmark_logic(user_id, star_id, s3_key, keywords, memo, summary):
    html = download_html_from_s3(s3_key)
    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(separator="\n")

    chunks = splitter.split_text(body_text)

    vectorstore = Chroma(
        persist_directory=settings.CHROMA_DB_URI,
        embedding_function=embeddings,
        collection_name="nebula_html",
    )

    existing_ids = vectorstore._collection.get(include=["ids"])["ids"]
    to_delete = [i for i in existing_ids if i.startswith(f"{star_id}-")]
    if to_delete:
        vectorstore.delete(ids=to_delete)

    ids = [f"{star_id}-{i}" for i in range(len(chunks))]
    metadatas = [
        dict(user_id=user_id, s3_key=s3_key,
             keywords=keywords, memo=memo, summary=summary)
        for _ in chunks
    ]

    vectorstore.add_texts(
        texts=chunks,
        ids=ids,
        metadatas=metadatas,
        embedding=embeddings.embed_documents,
    )
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
def save_bookmark_task(self, user_id, star_id, s3_key, keywords, memo, summary):
    return _save_bookmark_logic(user_id, star_id, s3_key, keywords, memo, summary)
