"""
Spring Boot API 클라이언트 서비스

Spring Boot 서버와 통신하여 북마크 관계를 Neo4j에 저장하고 조회하는 서비스입니다.
AI 서버는 Neo4j에 직접 접근하지 않고 Spring Boot를 경유합니다.
"""
import logging
from typing import List, Dict, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

import httpx
from pydantic import BaseModel

from app.core.config import settings

log = logging.getLogger(__name__)

class BookmarkRelationship(BaseModel):
    """북마크 관계 모델"""
    source_bookmark_id: str
    target_bookmark_id: str
    similarity_score: float
    relationship_type: str = "SIMILAR_TO"
    user_id: int
    created_at: Optional[str] = None

class BookmarkNode(BaseModel):
    """북마크 노드 모델"""
    bookmark_id: str
    title: str
    url: str
    user_id: int
    keywords: List[str]
    summary: str

class SpringBootService:
    """Spring Boot API 클라이언트 서비스"""
    
    def __init__(self):
        self.base_url = settings.SPRING_BOOT_BASE_URL
        self.timeout = 30.0
        
    async def create_bookmark_relationships(
        self, 
        new_bookmark: BookmarkNode,
        similar_bookmarks: List[Dict]
    ) -> bool:
        """
        새로운 북마크와 유사한 북마크들 간의 관계를 생성합니다.
        
        Args:
            new_bookmark: 새로 저장된 북마크 정보
            similar_bookmarks: 유사한 북마크들과 유사도 정보
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 1. 새 북마크 노드 생성
            await self._create_bookmark_node(new_bookmark)
            
            # 2. 관계 생성 요청 데이터 준비
            relationships = []
            for similar in similar_bookmarks:
                relationship = BookmarkRelationship(
                    source_bookmark_id=new_bookmark.bookmark_id,
                    target_bookmark_id=similar["bookmark_id"],
                    similarity_score=similar["similarity_score"],
                    user_id=new_bookmark.user_id
                )
                relationships.append(relationship)
                
                # 양방향 관계 생성 (선택사항)
                reverse_relationship = BookmarkRelationship(
                    source_bookmark_id=similar["bookmark_id"],
                    target_bookmark_id=new_bookmark.bookmark_id,
                    similarity_score=similar["similarity_score"],
                    user_id=new_bookmark.user_id
                )
                relationships.append(reverse_relationship)
            
            # 3. 배치로 관계 생성
            success = await self._batch_create_relationships(relationships)
            
            if success:
                log.info(
                    "북마크 %s에 대한 %d개의 관계가 생성되었습니다.",
                    new_bookmark.bookmark_id, len(similar_bookmarks)
                )
            
            return success
            
        except Exception as e:
            log.error("북마크 관계 생성 중 오류: %s", e)
            return False
    
    async def _create_bookmark_node(self, bookmark: BookmarkNode) -> bool:
        """북마크 노드를 Neo4j에 생성"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/bookmarks/nodes",
                    json=bookmark.model_dump(),
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 201:
                    log.debug("북마크 노드 생성 성공: %s", bookmark.bookmark_id)
                    return True
                elif response.status_code == 409:
                    # 이미 존재하는 노드 (정상)
                    log.debug("북마크 노드 이미 존재: %s", bookmark.bookmark_id)
                    return True
                else:
                    log.error(
                        "북마크 노드 생성 실패: %s, 응답: %s", 
                        response.status_code, response.text
                    )
                    return False
                    
        except httpx.TimeoutException:
            log.error("북마크 노드 생성 요청 타임아웃")
            return False
        except Exception as e:
            log.error("북마크 노드 생성 중 오류: %s", e)
            return False
    
    async def _batch_create_relationships(
        self, 
        relationships: List[BookmarkRelationship]
    ) -> bool:
        """북마크 관계들을 배치로 생성"""
        try:
            if not relationships:
                return True
                
            # 관계 데이터를 JSON으로 변환
            relationships_data = [rel.model_dump() for rel in relationships]
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/bookmarks/relationships/batch",
                    json={"relationships": relationships_data},
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code in [200, 201]:
                    log.debug("배치 관계 생성 성공: %d개", len(relationships))
                    return True
                else:
                    log.error(
                        "배치 관계 생성 실패: %s, 응답: %s",
                        response.status_code, response.text
                    )
                    return False
                    
        except httpx.TimeoutException:
            log.error("배치 관계 생성 요청 타임아웃")
            return False
        except Exception as e:
            log.error("배치 관계 생성 중 오류: %s", e)
            return False
    
    async def get_similar_bookmarks(
        self, 
        bookmark_id: str, 
        user_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        특정 북마크와 유사한 북마크들을 조회합니다.
        
        Args:
            bookmark_id: 기준 북마크 ID
            user_id: 사용자 ID
            limit: 조회할 최대 개수
            
        Returns:
            List[Dict]: 유사한 북마크들과 유사도 정보
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/bookmarks/{bookmark_id}/similar",
                    params={
                        "userId": user_id,
                        "limit": limit
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("similar_bookmarks", [])
                else:
                    log.error(
                        "유사 북마크 조회 실패: %s, 응답: %s",
                        response.status_code, response.text
                    )
                    return []
                    
        except Exception as e:
            log.error("유사 북마크 조회 중 오류: %s", e)
            return []
    
    async def get_bookmark_graph(
        self, 
        user_id: int,
        center_bookmark_id: Optional[str] = None,
        max_depth: int = 2
    ) -> Dict:
        """
        북마크 관계 그래프를 조회합니다.
        
        Args:
            user_id: 사용자 ID
            center_bookmark_id: 중심이 될 북마크 ID (없으면 전체 그래프)
            max_depth: 탐색할 최대 깊이
            
        Returns:
            Dict: 그래프 데이터 (노드와 엣지)
        """
        try:
            params = {
                "userId": user_id,
                "maxDepth": max_depth
            }
            
            if center_bookmark_id:
                params["centerBookmarkId"] = center_bookmark_id
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/bookmarks/graph",
                    params=params
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    log.error(
                        "북마크 그래프 조회 실패: %s, 응답: %s",
                        response.status_code, response.text
                    )
                    return {"nodes": [], "edges": []}
                    
        except Exception as e:
            log.error("북마크 그래프 조회 중 오류: %s", e)
            return {"nodes": [], "edges": []} 