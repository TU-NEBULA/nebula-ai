from app.core.embedding_model import EmbeddingModel
from app.core.chroma_db import ChromaDBClient
from app.external.s3_service import download_html_from_s3
from app.utils.text_processing import extract_main_text
from langchain.text_splitter import RecursiveCharacterTextSplitter

def save_html_to_chroma_db(id: str, user_id: str, s3_key: str):
    # 1) S3에서 HTML 파일 다운로드 후 주요 텍스트 추출
    html_content = download_html_from_s3(s3_key)
    main_text = extract_main_text(html_content)

    # 2) 텍스트 chunk 분할
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_text(main_text)

    # 3) ChromaDB 연결
    embedding_model = EmbeddingModel()
    chroma_db = ChromaDBClient()
    collection = chroma_db.get_or_create_collection()

    # 4) 새로 생성할 chunk들의 정보 준비
    embeddings = []
    docs = []
    metas = []
    ids = []

    for i, chunk in enumerate(chunks):
        docs.append(chunk)
        metas.append({
            "user_id": user_id,
            "doc_id": id,
            "chunk_index": i
        })
        # 예: "문서ID_chunk_순번"
        chunk_id = f"{id}_chunk_{i}"
        ids.append(chunk_id)

        # 임베딩 생성
        embeddings.append(embedding_model.get_embedding(chunk))

    # 5) 기존에 저장된 문서 chunk 조회
    #    - doc_id가 동일한 것들만 가져와서, 필요한 id 목록 추출
    existing_data = collection.get(
        where={"doc_id": id},  # doc_id가 일치하는 데이터만 조회
        # limit, n_results 등을 상황에 맞게 추가 가능
    )
    existing_ids = set(existing_data["ids"]) if existing_data and "ids" in existing_data else set()

    # 6) 새로 생성된 ID와 기존 ID 비교 -> 더 이상 사용되지 않는 chunk 삭제
    new_ids = set(ids)
    to_delete_ids = list(existing_ids - new_ids)
    if to_delete_ids:
        collection.delete(ids=to_delete_ids)

    # 7) 새 chunk 데이터를 추가(upsert)
    #    - 이미 존재하는 id라면 덮어쓰게 됨
    collection.upsert(
        embeddings=embeddings,
        documents=docs,
        ids=ids,
        metadatas=metas
    )

    # 8) 예시로 유사 문서 쿼리 진행
    distance_threshold = 0.5
    query_embedding = embedding_model.get_embedding(main_text)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=10,
        where={"user_id": user_id},
        include=["distances"]
    )

    found_ids = results["ids"][0] if "ids" in results else []
    found_distances = results["distances"][0] if "distances" in results else []

    similar_ids = []
    for d, chunk_id in zip(found_distances, found_ids):
        # 자기 자신 chunk는 제외
        if id in chunk_id:
            continue
        # 특정 거리 기준(0.5 미만)을 만족하는 경우만 수집
        if d < distance_threshold:
            similar_ids.append(chunk_id)

    return similar_ids
