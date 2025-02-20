from app.core.embedding_model import EmbeddingModel
from app.core.chroma_db import ChromaDBClient
from app.external.s3_service import download_html_from_s3
from app.utils.text_processing import extract_main_text
from langchain.text_splitter import RecursiveCharacterTextSplitter

def save_html_to_chroma_db(id: str, user_id: str, s3_key: str):
    # S3에서 HTML 파일 다운로드, 전처리, 텍스트 분할
    html_content = download_html_from_s3(s3_key)    
    main_text = extract_main_text(html_content)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,       # 최대 chunk 길이(문자 수 기준)
        chunk_overlap=50,     # 앞뒤 오버랩 길이(문자 수)
        length_function=len,  # 길이 계산용 함수 (기본값: len)
        separators=["\n\n", "\n", " ", ""]
        # 우선순위대로 \n\n -> \n -> 공백 -> 마지막엔 글자 단위로 분할
    )
    chunks = text_splitter.split_text(main_text)

    # 임베딩 및 ChromaDB에 저장
    embedding_model = EmbeddingModel()
    chroma_db = ChromaDBClient()

    collection = chroma_db.get_or_create_collection()

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
        ids.append(f"{id}_chunk_{i}")
        embeddings.append(embedding_model.get_embedding(chunk))

    collection.add(
        embeddings=embeddings,
        documents=docs,                 
        ids=ids,
        metadatas=metas
    )
    
    return 