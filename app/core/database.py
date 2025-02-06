from neo4j import GraphDatabase

NEO4J_URI = 
NEO4J_USER =
NEO4J_PASSWORD = 

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

def get_db_session():
    """
    FastAPI 요청 처리 시마다 세션을 yield하는 함수.
    with driver.session()을 통해 세션을 열고, 사용 완료 후 종료.
    """
    with driver.session() as session:
        yield session