"""
메시지 모델 테스트
"""
import pytest
import json
from datetime import datetime
from pydantic import ValidationError
from app.models.message_models import (
    BookmarkRelationshipMessage,
    BookmarkNodeData,
    SimilarBookmarkData
)


class TestBookmarkRelationshipMessage:
    """BookmarkRelationshipMessage 테스트"""
    
    def test_valid_message_creation(self):
        """유효한 메시지 생성 테스트"""
        
        source_bookmark = {
            "bookmark_id": "test_123",
            "title": "테스트 북마크",
            "url": "https://example.com",
            "keywords": ["테스트", "AI"],
            "summary": "테스트용 북마크입니다"
        }
        
        similar_bookmarks = [
            {
                "bookmark_id": "similar_1",
                "similarity_score": 0.85,
                "title": "유사한 북마크 1",
                "url": "https://example.com/1"
            },
            {
                "bookmark_id": "similar_2", 
                "similarity_score": 0.78,
                "title": "유사한 북마크 2",
                "url": "https://example.com/2"
            }
        ]
        
        message = BookmarkRelationshipMessage(
            user_id=123,
            source_bookmark=source_bookmark,
            similar_bookmarks=similar_bookmarks
        )
        
        assert message.user_id == 123
        assert message.source_bookmark == source_bookmark
        assert message.similar_bookmarks == similar_bookmarks
        assert isinstance(message.created_at, str)
    
    def test_message_serialization(self):
        """메시지 직렬화 테스트"""
        
        source_bookmark = {
            "bookmark_id": "test_123",
            "title": "테스트 북마크",
            "url": "https://example.com"
        }
        
        message = BookmarkRelationshipMessage(
            user_id=123,
            source_bookmark=source_bookmark,
            similar_bookmarks=[]
        )
        
        # model_dump() 테스트
        data = message.model_dump()
        assert "user_id" in data
        assert "source_bookmark" in data
        assert "similar_bookmarks" in data
        assert "created_at" in data
        
        # JSON 직렬화 테스트
        json_str = message.model_dump_json()
        assert isinstance(json_str, str)
        
        # JSON 파싱 테스트
        parsed = json.loads(json_str)
        assert parsed["user_id"] == 123
    
    def test_message_with_korean_content(self):
        """한글 콘텐츠 포함 메시지 테스트"""
        
        source_bookmark = {
            "bookmark_id": "korean_test",
            "title": "한글 제목",
            "url": "https://example.com",
            "keywords": ["한글", "키워드"],
            "summary": "한글로 작성된 요약입니다"
        }
        
        similar_bookmarks = [
            {
                "bookmark_id": "korean_similar",
                "similarity_score": 0.90,
                "title": "한글 유사 북마크",
                "url": "https://example.com/korean"
            }
        ]
        
        message = BookmarkRelationshipMessage(
            user_id=456,
            source_bookmark=source_bookmark,
            similar_bookmarks=similar_bookmarks
        )
        
        # JSON 직렬화에서 한글이 올바르게 처리되는지 확인
        json_str = message.model_dump_json()
        assert "한글 제목" in json_str
        assert "한글 유사 북마크" in json_str
    
    def test_empty_similar_bookmarks(self):
        """유사한 북마크가 없는 경우 테스트"""
        
        source_bookmark = {
            "bookmark_id": "lone_bookmark",
            "title": "고립된 북마크",
            "url": "https://example.com/lone"
        }
        
        message = BookmarkRelationshipMessage(
            user_id=789,
            source_bookmark=source_bookmark,
            similar_bookmarks=[]
        )
        
        assert len(message.similar_bookmarks) == 0
        assert isinstance(message.similar_bookmarks, list)
    
    def test_invalid_user_id(self):
        """잘못된 user_id 타입 테스트"""
        
        with pytest.raises(ValidationError):
            BookmarkRelationshipMessage(
                user_id="invalid_string",  # int가 아닌 string
                source_bookmark={"bookmark_id": "test"},
                similar_bookmarks=[]
            )
    
    def test_missing_required_fields(self):
        """필수 필드 누락 테스트"""
        
        # user_id 누락
        with pytest.raises(ValidationError):
            BookmarkRelationshipMessage(
                source_bookmark={"bookmark_id": "test"},
                similar_bookmarks=[]
            )
        
        # source_bookmark 누락
        with pytest.raises(ValidationError):
            BookmarkRelationshipMessage(
                user_id=123,
                similar_bookmarks=[]
            )
        
        # similar_bookmarks 누락
        with pytest.raises(ValidationError):
            BookmarkRelationshipMessage(
                user_id=123,
                source_bookmark={"bookmark_id": "test"}
            )


class TestBookmarkNodeData:
    """BookmarkNodeData 테스트"""
    
    def test_valid_node_creation(self):
        """유효한 노드 데이터 생성 테스트"""
        
        node = BookmarkNodeData(
            bookmark_id="node_123",
            title="노드 테스트",
            url="https://example.com/node",
            keywords=["노드", "테스트"],
            summary="노드 데이터 테스트입니다"
        )
        
        assert node.bookmark_id == "node_123"
        assert node.title == "노드 테스트"
        assert node.url == "https://example.com/node"
        assert node.keywords == ["노드", "테스트"]
        assert node.summary == "노드 데이터 테스트입니다"
    
    def test_node_serialization(self):
        """노드 데이터 직렬화 테스트"""
        
        node = BookmarkNodeData(
            bookmark_id="serialize_test",
            title="직렬화 테스트",
            url="https://example.com/serialize",
            keywords=["직렬화"],
            summary="직렬화 테스트"
        )
        
        data = node.model_dump()
        assert data["bookmark_id"] == "serialize_test"
        assert data["title"] == "직렬화 테스트"
        assert data["keywords"] == ["직렬화"]
    
    def test_empty_keywords(self):
        """빈 키워드 리스트 테스트"""
        
        node = BookmarkNodeData(
            bookmark_id="no_keywords",
            title="키워드 없는 북마크",
            url="https://example.com",
            keywords=[],
            summary="키워드가 없습니다"
        )
        
        assert len(node.keywords) == 0
        assert isinstance(node.keywords, list)


class TestSimilarBookmarkData:
    """SimilarBookmarkData 테스트"""
    
    def test_valid_similar_bookmark_creation(self):
        """유효한 유사 북마크 데이터 생성 테스트"""
        
        similar = SimilarBookmarkData(
            bookmark_id="similar_123",
            similarity_score=0.85,
            title="유사한 북마크",
            url="https://example.com/similar"
        )
        
        assert similar.bookmark_id == "similar_123"
        assert similar.similarity_score == 0.85
        assert similar.title == "유사한 북마크"
        assert similar.url == "https://example.com/similar"
    
    def test_similarity_score_range(self):
        """유사도 점수 범위 테스트"""
        
        # 정상 범위 (0.0 ~ 1.0)
        similar1 = SimilarBookmarkData(
            bookmark_id="test1",
            similarity_score=0.0,
            title="최소 유사도",
            url="https://example.com/min"
        )
        assert similar1.similarity_score == 0.0
        
        similar2 = SimilarBookmarkData(
            bookmark_id="test2",
            similarity_score=1.0,
            title="최대 유사도",
            url="https://example.com/max"
        )
        assert similar2.similarity_score == 1.0
        
        similar3 = SimilarBookmarkData(
            bookmark_id="test3",
            similarity_score=0.75,
            title="중간 유사도",
            url="https://example.com/mid"
        )
        assert similar3.similarity_score == 0.75
    
    def test_similarity_score_precision(self):
        """유사도 점수 정밀도 테스트"""
        
        similar = SimilarBookmarkData(
            bookmark_id="precision_test",
            similarity_score=0.123456789,
            title="정밀도 테스트",
            url="https://example.com/precision"
        )
        
        assert similar.similarity_score == 0.123456789
        
        # 직렬화 후에도 정밀도 유지 확인
        data = similar.model_dump()
        assert data["similarity_score"] == 0.123456789
    
    def test_invalid_similarity_score_type(self):
        """잘못된 유사도 점수 타입 테스트"""
        
        # Pydantic v2는 문자열을 float으로 자동 변환하므로
        # 변환할 수 없는 값으로 테스트
        with pytest.raises(ValidationError):
            SimilarBookmarkData(
                bookmark_id="invalid_score",
                similarity_score="invalid_string",  # 변환할 수 없는 문자열
                title="잘못된 점수",
                url="https://example.com/invalid"
            )


class TestMessageModelsIntegration:
    """메시지 모델 통합 테스트"""
    
    def test_complete_message_workflow(self):
        """완전한 메시지 워크플로우 테스트"""
        
        # 1. 노드 데이터 생성
        source_node = BookmarkNodeData(
            bookmark_id="workflow_source",
            title="워크플로우 소스",
            url="https://example.com/source",
            keywords=["워크플로우", "테스트"],
            summary="워크플로우 테스트용 소스 북마크"
        )
        
        # 2. 유사 북마크 데이터 생성
        similar1 = SimilarBookmarkData(
            bookmark_id="workflow_similar1",
            similarity_score=0.85,
            title="워크플로우 유사1",
            url="https://example.com/similar1"
        )
        
        similar2 = SimilarBookmarkData(
            bookmark_id="workflow_similar2",
            similarity_score=0.78,
            title="워크플로우 유사2",
            url="https://example.com/similar2"
        )
        
        # 3. 관계 메시지 생성
        relationship_message = BookmarkRelationshipMessage(
            user_id=999,
            source_bookmark=source_node.model_dump(),
            similar_bookmarks=[similar1.model_dump(), similar2.model_dump()]
        )
        
        # 4. 전체 검증
        assert relationship_message.user_id == 999
        assert len(relationship_message.similar_bookmarks) == 2
        assert relationship_message.source_bookmark["bookmark_id"] == "workflow_source"
        
        # 5. JSON 직렬화/역직렬화 테스트
        json_str = relationship_message.model_dump_json()
        parsed_data = json.loads(json_str)
        
        recreated_message = BookmarkRelationshipMessage(**parsed_data)
        assert recreated_message.user_id == relationship_message.user_id
        assert len(recreated_message.similar_bookmarks) == len(relationship_message.similar_bookmarks) 