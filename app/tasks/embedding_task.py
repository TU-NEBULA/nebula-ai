from app.core.celery_worker import celery
from app.core.embedding_model import EmbeddingModel
from app.core.chroma_db import ChromaDBClient
from app.external.s3_service import download_html_from_s3
from app.utils.text_processing import extract_main_text
from langchain.text_splitter import RecursiveCharacterTextSplitter

@celery.task(name="app.tasks.embedding_task.embed_bookmark")
def embed_bookmark(bookmark_id: str, user_id: str, s3_key: str):
    print(f"[START] Bookmark {bookmark_id} 임베딩 시작")
    try:
        html_content = download_html_from_s3(s3_key)
        main_text = extract_main_text(html_content)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        chunks = text_splitter.split_text(main_text)

        embedding_model = EmbeddingModel()
        chroma_db = ChromaDBClient()
        collection = chroma_db.get_or_create_collection()

        embeddings, docs, metas, ids = [], [], [], []

        for i, chunk in enumerate(chunks):
            docs.append(chunk)
            metas.append({
                "user_id": user_id,
                "doc_id": bookmark_id,
                "chunk_index": i,
                "s3_key": s3_key
            })
            ids.append(f"{bookmark_id}_chunk_{i}")
            embeddings.append(embedding_model.get_embedding(chunk))

        existing_data = collection.get(where={"doc_id": bookmark_id})
        existing_ids = set(existing_data["ids"]) if existing_data and "ids" in existing_data else set()
        to_delete_ids = list(existing_ids - set(ids))
        if to_delete_ids:
            collection.delete(ids=to_delete_ids)

        collection.upsert(
            embeddings=embeddings,
            documents=docs,
            ids=ids,
            metadatas=metas
        )
        print(f"[DONE] Bookmark {bookmark_id} 임베딩 완료")
    except Exception as e:
        print(f"[ERROR] Bookmark {bookmark_id} 처리 실패: {e}")
