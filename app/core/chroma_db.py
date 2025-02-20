import chromadb

from app.core.config import settings
from app.core.embedding_model import EmbeddingModel

class ChromaDBClient:
    CHROMA_DB_URI = settings.CHROMA_DB_URI
    DEFAULT_COLLECTION_NAME = "nebula_html"

    def __init__(self, db_uri: str = CHROMA_DB_URI):
        self.client = chromadb.PersistentClient(path=db_uri)

    def get_or_create_collection(self, collection_name: str = DEFAULT_COLLECTION_NAME, embedding_function=None):
        """
        주어진 컬렉션 이름으로 Chroma 컬렉션을 가져오거나 없으면 생성 후 반환
        embedding_function이 필요한 경우 인자로 받을 수 있도록 구성
        """
        return self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedding_function
        )
