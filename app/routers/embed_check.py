from fastapi import APIRouter, HTTPException, Path, Query
from app.core.chroma_db import ChromaDBClient
from app.core.embedding_model import EmbeddingModel

router = APIRouter()

@router.get("/embed/check/{bookmark_id}")
def check_embedding(
    bookmark_id: str = Path(..., description="북마크 ID"),
    user_id: str = Query(..., description="사용자 ID")
):
    chroma_db = ChromaDBClient()
    collection = chroma_db.get_or_create_collection()

    results = collection.get(
        where={"doc_id": bookmark_id},
        include=["documents", "metadatas"]
    )

    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])

    if not documents or not metadatas:
        raise HTTPException(status_code=404, detail=f"No embeddings found for bookmark_id: {bookmark_id}")

    embedding_model = EmbeddingModel()
    query_embedding = embedding_model.get_embedding(" ".join(documents))

    similar_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        where={"user_id": user_id},
        include=["metadatas"]
    )

    similar_doc_ids = set()
    for metadata_list in similar_results.get("metadatas", [[]])[0]:
        doc_id = metadata_list.get("doc_id")
        if doc_id and doc_id != bookmark_id:
            similar_doc_ids.add(doc_id)

    return {
        "bookmark_id": bookmark_id,
        "similar_doc_ids": list(similar_doc_ids)
    }


@router.get("/embed/all")
def get_all_embeddings(limit: int = 100):
    chroma_db = ChromaDBClient()
    collection = chroma_db.get_or_create_collection()

    results = collection.get(
        include=["metadatas", "documents"],
        limit=limit
    )

    metadatas = results.get("metadatas", [])
    documents = results.get("documents", [])

    if not metadatas or not documents:
        return {"message": "No embeddings found in the collection."}

    data = []
    for metadata, document in zip(metadatas, documents):
        data.append({
            "metadata": metadata,
            "document_preview": document[:100] 
        })

    return {
        "total_embeddings": len(data),
        "embeddings": data
    }
