from app.core.celery_worker import celery
from app.core.chroma_db import ChromaDBClient
from app.core.neo4j_client import Neo4jClient
from app.core.embedding_model import EmbeddingModel

@celery.task(
    name="app.tasks.keyword_sync_task.sync_user_keywords",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_jitter=True,
)
def sync_user_keywords(self, user_id: str):
    """
    Neo4J에서 사용자의 상위 키워드를 조회하여 Transformer 임베딩 후 ChromaDB에 저장
    """
    print(f"[START] Syncing keywords for user {user_id}")

    try:
        neo4j_client = Neo4jClient()
        keywords_data = neo4j_client.get_top_keywords(user_id=user_id, limit=300)
        neo4j_client.close()

        keywords = [data["keyword"] for data in keywords_data]
        weights = [data["weight"] for data in keywords_data]

        if not keywords:
            print(f"[WARNING] No keywords found for user {user_id}")
            return {"status": "no_keywords"}

        embedding_model = EmbeddingModel()
        keyword_embeddings = [embedding_model.get_embedding(kw) for kw in keywords]

        chroma_db = ChromaDBClient()
        collection = chroma_db.get_or_create_collection("user_keyword_embeddings")

        # 기존 데이터 삭제 (이전 키워드 정보 갱신)
        collection.delete(where={"user_id": user_id})

        # 새로운 키워드 데이터 추가
        ids = [f"{user_id}_keyword_{i}" for i in range(len(keywords))]
        metadatas = [{"user_id": user_id, "keyword": kw, "weight": wt} for kw, wt in zip(keywords, weights)]

        collection.upsert(
            embeddings=keyword_embeddings, 
            documents=keywords,
            ids=ids,
            metadatas=metadatas
        )

        print(f"[DONE] Keywords synced for user {user_id}")
        return {"status": "success", "user_id": user_id, "keywords": keywords}

    except Exception as e:
        print(f"[ERROR] Keyword sync failed: {e}")
        self.retry(exc=e)
        return {"status": "failed", "error": str(e)}
