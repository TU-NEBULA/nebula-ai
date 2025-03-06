from app.core.celery_worker import celery
from app.core.embedding_model import EmbeddingModel
from app.core.chroma_db import ChromaDBClient

@celery.task(
    name="app.tasks.similarity_task.calculate_similarity",
    bind=True,  # self로 태스크 인스턴스 접근 가능
    autoretry_for=(Exception,),  # 예외 발생 시 자동 재시도
    retry_kwargs={'max_retries': 3, 'countdown': 60},  # 최대 3회, 60초 간격 재시도
    retry_backoff=True,  # 재시도 간격 증가
    retry_jitter=True,  # 랜덤 지연 추가
)
def calculate_similarity(self, data):
    bookmark_id = data["bookmark_id"]
    user_id = data["user_id"]
    print(f"[START] Similarity check for bookmark {bookmark_id}")
    
    try:
        chroma_db = ChromaDBClient()
        collection = chroma_db.get_or_create_collection()

        results = collection.get(
            where={"doc_id": bookmark_id},
            include=["documents"]
        )

        documents = results.get("documents", [])
        if not documents:
            print(f"[ERROR] No documents found for bookmark {bookmark_id}")
            return {"status": "failed", "reason": "no documents"}

        embedding_model = EmbeddingModel()
        query_embedding = embedding_model.get_embedding(" ".join(documents))

        similar_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=50,
            where={"user_id": user_id},
            include=["distances", "metadatas"]
        )

        all_distances = similar_results.get("distances", [[]])[0]
        all_metadatas = similar_results.get("metadatas", [[]])[0]

        filtered_results = [
            {"doc_id": meta["doc_id"], "distance": distance}
            for meta, distance in zip(all_metadatas, all_distances)
            if meta["doc_id"] != bookmark_id and distance <= 0.5
        ]

        print(f"[DONE] Similarity check for bookmark {bookmark_id}")
        return {
            "bookmark_id": bookmark_id,
            "similarity_scores": filtered_results
        }

    except Exception as e:
        print(f"[ERROR] Similarity check failed: {e}")
        raise self.retry(exc=e)
