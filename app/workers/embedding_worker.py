import pika
import json
from app.core.embedding_model import EmbeddingModel
from app.core.chroma_db import ChromaDBClient
from app.external.s3_service import download_html_from_s3
from app.utils.text_processing import extract_main_text
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.core.config import settings

RABBITMQ_HOST = settings.RABBITMQ_HOST
RABBITMQ_QUEUE = settings.RABBITMQ_QUEUE

def process_embedding(message):
    bookmark_id = message["id"]
    s3_key = message["s3_key"]
    user_id = message["user_id"]

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

def callback(ch, method, properties, body):
    message = json.loads(body)
    print(f"[x] Received message: {message}")
    try:
        process_embedding(message)
        print(f"[✔] Processed bookmark {message['id']}")
    except Exception as e:
        print(f"[✖] Failed to process {message['id']}: {e}")
    ch.basic_ack(delivery_tag=method.delivery_tag)

def run_worker():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST)
    )
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

    print("[*] Waiting for messages.")
    channel.start_consuming()

if __name__ == "__main__":
    run_worker()
