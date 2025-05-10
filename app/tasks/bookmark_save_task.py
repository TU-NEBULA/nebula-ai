from app.core.celery_worker import celery
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.external.s3_service import download_html_from_s3
from app.core.chroma_db import ChromaDBClient

chroma_client = ChromaDBClient()
embeddings = OpenAIEmbeddings(model=settings.OPENAI_EMBED_MODEL or "text-embedding-3-small")


@celery.task(
    name="tasks.save_bookmark",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_jitter=True,
)
def save_bookmark_task(self, user_id, star_id, s3_key, keywords, memo, summary):

    html = download_html_from_s3(s3_key)
    soup = BeautifulSoup(html, "html.parser")
    body_text = soup.get_text(separator="\n")

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(body_text)

    collection = chroma_client.get_or_create_collection(
        collection_name="nebula_html",
        embedding_function=embeddings
    )

    existing_ids = [doc.id for doc in collection.get(include=["ids","metadatas"]) 
                    if doc.id.startswith(f"{star_id}-")]
    if existing_ids:
        collection.delete(ids=existing_ids)

    ids = [f"{star_id}-{i}" for i in range(len(chunks))]
    metadatas = [{
        "user_id": user_id,
        "s3_key": s3_key,
        "keywords": keywords,
        "memo": memo,
        "summary": summary,
    } for _ in chunks]

    collection.add(
        documents=chunks,
        ids=ids,
        metadatas=metadatas
    )

    chroma_client.client.persist()

    return {"status": "success", "inserted": len(chunks)}
