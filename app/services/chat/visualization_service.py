"""
북마크 시각화 서비스

RAG 검색 결과를 그래프 데이터로 변환하여 시각화 지원
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone


class VisualizationService:
    """북마크 시각화를 담당하는 서비스 클래스"""
    
    def __init__(self):
        self.color_map = {
            'bookmark': '#4F46E5',     # 보라색
            'document': '#059669',     # 초록색  
            'article': '#DC2626',      # 빨간색
            'note': '#D97706',         # 주황색
            'webpage': '#0891B2'       # 파란색
        }
        
    def create_bookmark_visualization(
        self,
        ctx_blocks: List[Tuple[str, Dict[str, Any]]],
        search_query: str
    ) -> Dict[str, Any]:
        """
        RAG 검색 결과를 북마크 시각화용 그래프 데이터로 변환합니다.
        
        Args:
            ctx_blocks: RAG 검색 결과 [(snippet, metadata), ...]
            search_query: 검색 쿼리
            
        Returns:
            시각화용 그래프 데이터 (nodes, edges, layout 정보 포함)
        """
        if not ctx_blocks:
            return self._create_empty_visualization(search_query)

        # 노드 생성
        nodes = self._create_nodes(ctx_blocks)
        
        # 엣지 생성 
        edges = self._create_edges(nodes)
        
        # 레이아웃 결정
        layout_type = self._determine_layout(nodes, edges)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "layout": layout_type,
            "total_bookmarks": len(nodes),
            "search_query": search_query,
            "visualization_type": "bookmark_network",
            "statistics": self._calculate_statistics(nodes, edges),
            "interaction_hints": self._get_interaction_hints()
        }

    def _create_empty_visualization(self, search_query: str) -> Dict[str, Any]:
        """빈 시각화 데이터 생성"""
        return {
            "nodes": [],
            "edges": [],
            "layout": "force-3d",
            "total_bookmarks": 0,
            "search_query": search_query,
            "visualization_type": "bookmark_network"
        }

    def _create_nodes(self, ctx_blocks: List[Tuple[str, Dict[str, Any]]]) -> List[Dict]:
        """북마크 데이터에서 노드들을 생성"""
        nodes = []
        
        for i, (snippet, metadata) in enumerate(ctx_blocks):
            # 유사도 점수에 따른 노드 크기 계산
            score = metadata.get('score', 0)
            node_size = max(10, min(30, int(score * 40)))  # 10-30 범위
            
            # 소스 타입에 따른 색상 구분
            source_type = metadata.get('source_type', 'bookmark')
            node_color = self.color_map.get(source_type, '#6B7280')
            
            node = {
                "id": f"bookmark_{metadata.get('source_id', i)}",
                "label": metadata.get('title', '(제목없음)')[:30],
                "title": metadata.get('title', '(제목없음)'),
                "url": metadata.get('url', ''),
                "snippet": snippet,
                "keywords": metadata.get('keywords', []),
                "source_type": source_type,
                "similarity_score": float(score),
                "size": int(node_size),
                "color": node_color,
                "x": i * 100,  # 기본 배치
                "y": score * 100,
                "z": i * 50
            }
            nodes.append(node)
            
        return nodes

    def _create_edges(self, nodes: List[Dict]) -> List[Dict]:
        """노드들 사이의 연결 관계를 나타내는 엣지들을 생성"""
        edges = []
        
        # 1. 키워드 기반 연결
        edges.extend(self._create_keyword_edges(nodes))
        
        # 2. 유사도 점수 기반 연결
        edges.extend(self._create_similarity_edges(nodes, edges))
        
        return edges

    def _create_keyword_edges(self, nodes: List[Dict]) -> List[Dict]:
        """키워드 기반 노드 연결"""
        edges = []
        
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                node_a = nodes[i]
                node_b = nodes[j]
                
                # 공통 키워드 찾기
                keywords_a = set(node_a.get('keywords', []))
                keywords_b = set(node_b.get('keywords', []))
                shared_keywords = keywords_a & keywords_b
                
                if shared_keywords:
                    # 공통 키워드 수에 따른 연결 강도
                    connection_weight = len(shared_keywords)
                    edge_width = max(1, min(5, connection_weight))
                    
                    edge = {
                        "id": f"edge_{node_a['id']}_{node_b['id']}",
                        "source": node_a['id'],
                        "target": node_b['id'],
                        "weight": connection_weight,
                        "width": edge_width,
                        "color": "#94A3B8",
                        "shared_keywords": list(shared_keywords),
                        "connection_type": "keyword_similarity"
                    }
                    edges.append(edge)
                    
        return edges

    def _create_similarity_edges(self, nodes: List[Dict], existing_edges: List[Dict]) -> List[Dict]:
        """유사도 점수 기반 노드 연결"""
        edges = []
        high_similarity_nodes = [node for node in nodes if node['similarity_score'] > 0.8]
        
        if len(high_similarity_nodes) <= 1:
            return edges
            
        for i in range(len(high_similarity_nodes)):
            for j in range(i + 1, len(high_similarity_nodes)):
                node_a = high_similarity_nodes[i]
                node_b = high_similarity_nodes[j]
                
                # 이미 키워드로 연결되어 있으면 건너뛰기
                existing_edge = any(
                    edge['source'] == node_a['id'] and edge['target'] == node_b['id']
                    for edge in existing_edges
                )
                
                if not existing_edge:
                    edge = {
                        "id": f"edge_similarity_{node_a['id']}_{node_b['id']}",
                        "source": node_a['id'],
                        "target": node_b['id'],
                        "weight": 0.5,
                        "width": 2,
                        "color": "#F59E0B",
                        "connection_type": "high_similarity"
                    }
                    edges.append(edge)
                    
        return edges

    def _determine_layout(self, nodes: List[Dict], edges: List[Dict]) -> str:
        """노드와 엣지 수에 따라 최적의 레이아웃을 결정"""
        node_count = len(nodes)
        edge_count = len(edges)
        
        if node_count <= 3:
            return "linear"
        elif node_count <= 6:
            return "circular" 
        elif edge_count > node_count * 0.7:
            return "force-3d"  # 연결이 많으면 3D 포스 레이아웃
        elif edge_count < node_count * 0.3:
            return "grid"      # 연결이 적으면 그리드 레이아웃
        else:
            return "force-2d"  # 기본 2D 포스 레이아웃

    def _calculate_statistics(self, nodes: List[Dict], edges: List[Dict]) -> Dict[str, Any]:
        """시각화 통계 정보 계산"""
        if not nodes:
            return {
                "total_connections": 0,
                "avg_similarity": 0.0,
                "source_types": [],
                "keyword_distribution": {},
                "similarity_range": {"min": 0.0, "max": 0.0}
            }
            
        return {
            "total_connections": int(len(edges)),
            "avg_similarity": float(sum(node['similarity_score'] for node in nodes) / len(nodes)),
            "source_types": list(set(node['source_type'] for node in nodes)),
            "keyword_distribution": self._get_keyword_distribution(nodes),
            "similarity_range": {
                "min": float(min(node['similarity_score'] for node in nodes)),
                "max": float(max(node['similarity_score'] for node in nodes))
            }
        }

    def _get_keyword_distribution(self, nodes: List[Dict]) -> Dict[str, int]:
        """노드들의 키워드 분포를 계산"""
        keyword_count = {}
        
        for node in nodes:
            keywords = node.get('keywords', [])
            for keyword in keywords:
                keyword_count[keyword] = keyword_count.get(keyword, 0) + 1
        
        # 상위 10개 키워드만 반환
        sorted_keywords = sorted(keyword_count.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_keywords[:10])

    def _get_interaction_hints(self) -> Dict[str, Any]:
        """사용자 인터랙션 힌트 제공"""
        return {
            "node_hover": "북마크 상세 정보 확인",
            "node_click": "북마크 링크로 이동",
            "edge_hover": "연결 관계 확인",
            "layout_options": ["force-3d", "circular", "hierarchical", "grid"]
        }

    def create_empty_visualization_message(self) -> Dict[str, Any]:
        """검색 결과가 없을 때의 기본 시각화 메시지"""
        return {
            "type": "visualization", 
            "data": {
                "graph_payload": {
                    "nodes": [],
                    "edges": [],
                    "layout": "empty",
                    "message": "관련 북마크를 찾지 못했습니다"
                },
                "context_info": {
                    "total_documents": 0,
                    "search_successful": False,
                    "message": "검색 결과가 없습니다"
                }
            }
        }

    def create_visualization_message(
        self,
        ctx_blocks: List[Tuple[str, Dict[str, Any]]],
        search_query: str
    ) -> Dict[str, Any]:
        """시각화 데이터 메시지 생성"""
        if not ctx_blocks:
            return self.create_empty_visualization_message()
            
        visualization_data = self.create_bookmark_visualization(ctx_blocks, search_query)
        
        return {
            "type": "visualization",
            "data": {
                "graph_payload": visualization_data,
                "context_info": {
                    "total_documents": len(ctx_blocks),
                    "search_successful": True,
                    "avg_similarity": visualization_data['statistics']['avg_similarity'],
                    "search_query": search_query,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                "filter_options": {
                    "by_source_type": visualization_data['statistics']['source_types'],
                    "by_similarity": ["high", "medium", "low"],
                    "by_keywords": list(visualization_data['statistics']['keyword_distribution'].keys())
                },
                "sort_options": {
                    "similarity_desc": "유사도 높은순",
                    "similarity_asc": "유사도 낮은순", 
                    "title_asc": "제목 가나다순",
                    "keywords_desc": "키워드 많은순"
                }
            }
        }


# 싱글톤 인스턴스
visualization_service = VisualizationService() 