from contextlib import contextmanager
from neo4j import GraphDatabase
from app.core.config import settings 

driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

@contextmanager
def get_db_session():
    """
    FastAPI 요청 처리 시마다 Neo4j 세션을 제공하는 컨텍스트 관리자.
    """
    session = driver.session()
    try:
        yield session  # 세션을 반환
    finally:
        session.close()  # 요청이 끝나면 세션 종료
