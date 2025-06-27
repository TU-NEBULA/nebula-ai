"""
모델 패키지 초기화

이 모듈은 모든 데이터베이스 모델들을 중앙에서 관리합니다.
"""

# 기본 모델
from .base import BaseModel

# 북마크 관련 모델
from .bookmark import (
    BookmarkAIStatus, BookmarkAIStatusCreate, BookmarkAIStatusRead, BookmarkAIStatusUpdate,
    DocumentChunk, DocumentChunkCreate, DocumentChunkRead,
    UserAIProfile, UserAIProfileCreate, UserAIProfileRead, UserAIProfileUpdate
)

# 채팅 관련 모델
from .chat import (
    ChatSession, ChatSessionCreate, ChatSessionRead, ChatSessionUpdate,
    ChatMessage, ChatMessageCreate, ChatMessageRead,
    UserFeedback, UserFeedbackCreate, UserFeedbackRead,
    RAGReference, RAGReferenceCreate, RAGReferenceRead,
    DocumentVector, DocumentVectorCreate, DocumentVectorRead, DocumentVectorUpdate,
    VectorSearchResult, VectorSearchRequest
)

# 사용자 프로필 및 추천 시스템 모델
from .user_profile import (
    # 사용자 프로필
    UserProfile, UserProfileCreate, UserProfileRead, UserProfileUpdate,
    
    # 사용자 유사도
    UserSimilarity, UserSimilarityCreate, UserSimilarityRead,
    
    # 추천 시스템
    Recommendation, RecommendationCreate, RecommendationRead, RecommendationUpdate,
    
    # 트렌드 분석
    TrendAnalysis, TrendAnalysisCreate, TrendAnalysisRead,
    
    # 컨텍스트 기반 추천
    ContextualRecommendation, ContextualRecommendationCreate, ContextualRecommendationRead,
    
    # 학습 경로
    LearningPath, LearningPathCreate, LearningPathRead,
    
    # 사용자 학습 진도
    UserLearningProgress, UserLearningProgressCreate, UserLearningProgressRead,
    
    # 세션 컨텍스트
    SessionContext, SessionContextCreate, SessionContextRead
)

# 메시지 모델
from .message_models import BookmarkRelationshipMessage, BookmarkNodeData, SimilarBookmarkData

# 추출 데이터 모델
from .extract_data import ExtractDataModel

# 전체 모델 리스트 (마이그레이션용)
__all__ = [
    # 기본 모델
    "BaseModel",
    
    # 북마크 관련
    "BookmarkAIStatus", "BookmarkAIStatusCreate", "BookmarkAIStatusRead", "BookmarkAIStatusUpdate",
    "DocumentChunk", "DocumentChunkCreate", "DocumentChunkRead",
    "UserAIProfile", "UserAIProfileCreate", "UserAIProfileRead", "UserAIProfileUpdate",
    
    # 채팅 관련
    "ChatSession", "ChatSessionCreate", "ChatSessionRead", "ChatSessionUpdate",
    "ChatMessage", "ChatMessageCreate", "ChatMessageRead",
    "UserFeedback", "UserFeedbackCreate", "UserFeedbackRead",
    "RAGReference", "RAGReferenceCreate", "RAGReferenceRead",
    "DocumentVector", "DocumentVectorCreate", "DocumentVectorRead", "DocumentVectorUpdate",
    "VectorSearchResult", "VectorSearchRequest",
    
    # 사용자 프로필 및 추천 시스템
    "UserProfile", "UserProfileCreate", "UserProfileRead", "UserProfileUpdate",
    "UserSimilarity", "UserSimilarityCreate", "UserSimilarityRead",
    "Recommendation", "RecommendationCreate", "RecommendationRead", "RecommendationUpdate",
    "TrendAnalysis", "TrendAnalysisCreate", "TrendAnalysisRead",
    "ContextualRecommendation", "ContextualRecommendationCreate", "ContextualRecommendationRead",
    "LearningPath", "LearningPathCreate", "LearningPathRead",
    "UserLearningProgress", "UserLearningProgressCreate", "UserLearningProgressRead",
    "SessionContext", "SessionContextCreate", "SessionContextRead",
    
    # 메시지 및 추출 데이터
    "BookmarkRelationshipMessage", "BookmarkNodeData", "SimilarBookmarkData",
    "ExtractDataModel"
]

# 새로 추가된 클러스터링 모델들
from .clustering import (
    # 클러스터 관련 모델
    UserCluster, UserClusterCreate, UserClusterRead, UserClusterUpdate,
    UserClusterMembership, UserClusterMembershipCreate, UserClusterMembershipRead,
    ClusterKeywords, ClusterKeywordsCreate, ClusterKeywordsRead,
    ClusterQualityMetrics, ClusterQualityMetricsCreate, ClusterQualityMetricsRead,
    ClusteringJobHistory, ClusteringJobHistoryCreate, ClusteringJobHistoryRead
)

__all__ += [
    # 새로 추가된 클러스터링 모델들
    "UserCluster", "UserClusterCreate", "UserClusterRead", "UserClusterUpdate",
    "UserClusterMembership", "UserClusterMembershipCreate", "UserClusterMembershipRead",
    "ClusterKeywords", "ClusterKeywordsCreate", "ClusterKeywordsRead",
    "ClusterQualityMetrics", "ClusterQualityMetricsCreate", "ClusterQualityMetricsRead",
    "ClusteringJobHistory", "ClusteringJobHistoryCreate", "ClusteringJobHistoryRead",
]
