from neo4j import GraphDatabase
from config import settings 

driver = GraphDatabase.driver(
    settings.NEO4J_URI,
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

def get_db_session():
    """
    FastAPI 요청 처리 시마다 Neo4j 세션을 yield하는 함수.
    with driver.session()을 통해 세션을 열고, 사용 완료 후 자동 종료.
    """
    with driver.session() as session:
        yield session
