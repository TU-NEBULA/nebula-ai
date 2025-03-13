from neo4j import GraphDatabase
from app.core.config import settings

class Neo4jClient:
    def __init__(self, uri=settings.NEO4J_URI, user=settings.NEO4J_USER, password=settings.NEO4J_PASSWORD):
        """Neo4j 데이터베이스 연결 설정"""
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """데이터베이스 연결 종료"""
        self._driver.close()

    def get_top_keywords(self, user_id: str, limit: int = 100):
        """
        사용자가 가장 많이 사용한 키워드 상위 limit개 조회
        """
        query = """
        MATCH (u:User {user_id: $user_id})-[:CREATED]->(s:Star)-[:TAGGED]->(k:keyword)
        RETURN k.name AS keyword, COUNT(s) AS weight
        ORDER BY weight DESC
        LIMIT $limit
        """
        with self._driver.session() as session:
            result = session.run(query, user_id=user_id, limit=limit)
            return [{"keyword": record["keyword"], "weight": record["weight"]} for record in result]
