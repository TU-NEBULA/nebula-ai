"""
북마크 그래프 API 라우터

북마크 간의 유사도 관계 그래프를 조회하고 시각화 데이터를 제공하는 API 엔드포인트입니다.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.external.springboot_service import SpringBootService

log = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])

# 서비스 인스턴스
springboot_service = SpringBootService()

class GraphResponse(BaseModel):
    """그래프 조회 응답 모델"""
    nodes: list
    edges: list
    total_nodes: int
    total_edges: int
    center_bookmark_id: Optional[str] = None

class SimilarBookmarksResponse(BaseModel):
    """유사 북마크 조회 응답 모델"""
    bookmark_id: str
    similar_bookmarks: list
    total_count: int

@router.get(
    "/similarity/{bookmark_id}",
    response_model=SimilarBookmarksResponse,
    summary="특정 북마크와 유사한 북마크들 조회",
    description="지정된 북마크와 유사도가 높은 북마크들을 조회합니다."
)
async def get_similar_bookmarks(
    bookmark_id: str,
    user_id: int = Query(..., description="사용자 ID"),
    limit: int = Query(default=10, ge=1, le=50, description="조회할 최대 개수")
):
    """
    특정 북마크와 유사한 북마크들을 조회합니다.
    
    Args:
        bookmark_id: 기준 북마크 ID
        user_id: 사용자 ID
        limit: 조회할 최대 개수
        
    Returns:
        SimilarBookmarksResponse: 유사한 북마크들과 메타데이터
    """
    try:
        similar_bookmarks = await springboot_service.get_similar_bookmarks(
            bookmark_id=bookmark_id,
            user_id=user_id,
            limit=limit
        )
        
        return SimilarBookmarksResponse(
            bookmark_id=bookmark_id,
            similar_bookmarks=similar_bookmarks,
            total_count=len(similar_bookmarks)
        )
        
    except Exception as e:
        log.error("유사 북마크 조회 중 오류: %s", e)
        raise HTTPException(
            status_code=500,
            detail="유사 북마크 조회 중 오류가 발생했습니다."
        )

@router.get(
    "/user/{user_id}",
    response_model=GraphResponse,
    summary="사용자의 북마크 관계 그래프 조회",
    description="사용자의 모든 북마크 간 관계를 그래프 형태로 조회합니다."
)
async def get_user_bookmark_graph(
    user_id: int,
    center_bookmark_id: Optional[str] = Query(
        None, 
        description="중심 북마크 ID (없으면 전체 그래프)"
    ),
    max_depth: int = Query(
        default=2, 
        ge=1, 
        le=5, 
        description="탐색할 최대 깊이"
    )
):
    """
    사용자의 북마크 관계 그래프를 조회합니다.
    
    Args:
        user_id: 사용자 ID
        center_bookmark_id: 중심 북마크 ID (선택사항)
        max_depth: 탐색할 최대 깊이
        
    Returns:
        GraphResponse: 그래프 노드와 엣지 데이터
    """
    try:
        graph_data = await springboot_service.get_bookmark_graph(
            user_id=user_id,
            center_bookmark_id=center_bookmark_id,
            max_depth=max_depth
        )
        
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        return GraphResponse(
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
            center_bookmark_id=center_bookmark_id
        )
        
    except Exception as e:
        log.error("북마크 그래프 조회 중 오류: %s", e)
        raise HTTPException(
            status_code=500,
            detail="북마크 그래프 조회 중 오류가 발생했습니다."
        )

@router.get(
    "/network/{user_id}",
    response_model=Dict[str, Any],
    summary="D3.js용 네트워크 그래프 데이터 조회",
    description="D3.js나 기타 시각화 라이브러리에서 사용할 수 있는 형태로 그래프 데이터를 제공합니다."
)
async def get_network_graph_data(
    user_id: int,
    center_bookmark_id: Optional[str] = Query(None, description="중심 북마크 ID"),
    similarity_threshold: float = Query(
        default=0.7, 
        ge=0.0, 
        le=1.0, 
        description="유사도 임계값"
    )
):
    """
    네트워크 시각화를 위한 그래프 데이터를 조회합니다.
    
    D3.js, Cytoscape.js 등의 시각화 라이브러리에서 바로 사용할 수 있는
    형태로 노드와 링크 데이터를 제공합니다.
    
    Args:
        user_id: 사용자 ID
        center_bookmark_id: 중심 북마크 ID
        similarity_threshold: 유사도 임계값
        
    Returns:
        Dict: 네트워크 시각화 데이터
        {
            "nodes": [...],
            "links": [...],
            "metadata": {...}
        }
    """
    try:
        graph_data = await springboot_service.get_bookmark_graph(
            user_id=user_id,
            center_bookmark_id=center_bookmark_id,
            max_depth=3
        )
        
        # 원본 데이터 변환
        nodes = []
        links = []
        
        # 노드 데이터 변환 (D3.js 형식)
        for node in graph_data.get("nodes", []):
            nodes.append({
                "id": node.get("bookmark_id"),
                "title": node.get("title", ""),
                "url": node.get("url", ""),
                "keywords": node.get("keywords", []),
                "group": _get_node_group(node.get("keywords", [])),
                "size": node.get("importance_score", 1.0)
            })
        
        # 엣지 데이터 변환 (D3.js links 형식)
        for edge in graph_data.get("edges", []):
            similarity = edge.get("similarity_score", 0.0)
            
            # 유사도 임계값 필터링
            if similarity >= similarity_threshold:
                links.append({
                    "source": edge.get("source_bookmark_id"),
                    "target": edge.get("target_bookmark_id"),
                    "weight": similarity,
                    "strength": similarity * 10,  # 시각적 표현용
                    "type": edge.get("relationship_type", "similar")
                })
        
        return {
            "nodes": nodes,
            "links": links,
            "metadata": {
                "total_nodes": len(nodes),
                "total_links": len(links),
                "center_node": center_bookmark_id,
                "similarity_threshold": similarity_threshold,
                "user_id": user_id
            }
        }
        
    except Exception as e:
        log.error("네트워크 그래프 데이터 조회 중 오류: %s", e)
        raise HTTPException(
            status_code=500,
            detail="네트워크 그래프 데이터 조회 중 오류가 발생했습니다."
        )

def _get_node_group(keywords: list) -> int:
    """
    키워드를 기반으로 노드 그룹을 결정합니다.
    
    시각화에서 색상이나 모양을 다르게 표시하기 위한 그룹 번호를 반환합니다.
    
    Args:
        keywords: 북마크의 키워드 리스트
        
    Returns:
        int: 그룹 번호 (0-9)
    """
    if not keywords:
        return 0
    
    # 주요 카테고리별 그룹 분류
    tech_keywords = ["python", "javascript", "api", "database", "machine learning", "ai"]
    business_keywords = ["business", "startup", "marketing", "finance", "strategy"]
    design_keywords = ["design", "ui", "ux", "frontend", "css"]
    
    keywords_lower = [k.lower() for k in keywords]
    
    for keyword in keywords_lower:
        if any(tech in keyword for tech in tech_keywords):
            return 1  # 기술
        elif any(biz in keyword for biz in business_keywords):
            return 2  # 비즈니스
        elif any(design in keyword for design in design_keywords):
            return 3  # 디자인
    
    # 첫 번째 키워드의 해시값 기반 그룹
    return abs(hash(keywords[0])) % 7 + 4 