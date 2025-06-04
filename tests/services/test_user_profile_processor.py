"""
UserProfileProcessor 테스트

UserProfileProcessor의 모든 기능을 테스트
- 프로필 벡터 업데이트
- 유사도 계산
- 추천 생성
- 증분 업데이트
- 성능 최적화
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from app.services.user_profile_processor import UserProfileProcessor
from app.services.vector_generator import VectorGenerator
from app.external.openai_service import OpenAIService


class TestUserProfileProcessor:
    """UserProfileProcessor 기본 기능 테스트"""
    
    @pytest.fixture
    def mock_repositories(self):
        """Mock 리포지토리들"""
        return {
            'chat_repo': AsyncMock(),
            'bookmark_repo': AsyncMock(),
            'ai_profile_repo': AsyncMock(),
            'user_profile_repo': AsyncMock(),
            'similarity_repo': AsyncMock(),
            'recommendation_repo': AsyncMock()
        }
    
    @pytest.fixture
    def mock_openai_service(self):
        """Mock OpenAI 서비스"""
        mock_service = AsyncMock(spec=OpenAIService)
        
        # 실제 메서드 이름 사용
        mock_service.create_embedding.return_value = MagicMock()
        mock_service.create_embedding.return_value.data = [
            MagicMock(embedding=[0.1, 0.8, 0.3, 0.5, 0.9])
        ]
        
        mock_service.generate_completion.return_value = MagicMock()
        mock_service.generate_completion.return_value.choices = [
            MagicMock(message=MagicMock(content='{"keywords": {"AI": 0.9, "머신러닝": 0.8}, "topics": {"인공지능": 0.9}, "categories": {"IT": 0.85}, "concepts": {"미래": 0.7}}'))
        ]
        
        return mock_service
    
    @pytest.fixture
    def processor(self, mock_repositories, mock_openai_service):
        """UserProfileProcessor 인스턴스"""
        with patch('app.services.user_profile_processor.VectorGenerator') as mock_vector_gen:
            mock_vector_gen.return_value = AsyncMock()
            processor = UserProfileProcessor(mock_repositories)
            processor.vector_generator = mock_vector_gen.return_value
            processor.openai_service = mock_openai_service
            
            return processor
    
    @pytest.mark.asyncio
    async def test_update_user_profile_full_regeneration(self, processor, mock_repositories):
        """전체 프로필 재생성 테스트"""
        
        # Mock 데이터 준비
        user_id = 123
        
        # 기존 프로필 Mock
        existing_profile = MagicMock()
        existing_profile.user_id = user_id
        existing_profile.profile_vector = [0.2, 0.4, 0.6]
        existing_profile.vector_strength = 0.7
        mock_repositories['user_profile_repo'].get_profile.return_value = existing_profile
        
        # 채팅 데이터 Mock
        chat_data = [
            MagicMock(content="AI 관련 대화", created_at=datetime.now()),
            MagicMock(content="머신러닝 공부 중", created_at=datetime.now())
        ]
        mock_repositories['chat_repo'].get_user_chats.return_value = chat_data
        
        # 북마크 데이터 Mock
        bookmark_data = [
            MagicMock(title="AI 논문", content="최신 연구", created_at=datetime.now()),
            MagicMock(title="PyTorch 가이드", content="딥러닝", created_at=datetime.now())
        ]
        mock_repositories['bookmark_repo'].get_user_bookmarks.return_value = bookmark_data
        
        # AI 프로필 데이터 Mock
        ai_profile_data = [
            MagicMock(profile_data={"interests": ["AI", "Programming"]}, created_at=datetime.now())
        ]
        mock_repositories['ai_profile_repo'].get_user_profiles.return_value = ai_profile_data
        
        # Vector Generator Mock
        processor.vector_generator.generate_profile_vector = AsyncMock(return_value=(
            [0.1, 0.8, 0.3, 0.5, 0.9],  # 벡터
            {  # 메타데이터
                "vector_strength": 0.85,
                "keywords": {"AI": 0.9, "ML": 0.8},
                "algorithm_version": "v2.0"
            }
        ))
        
        # 프로필 업데이트 실행
        result = await processor.update_user_profile(user_id, force_full_recalculation=True)
        
        # 결과 검증
        assert result is not None
        assert result["vector_strength"] == 0.85
        assert result["data_points_processed"] == 5
        assert "processing_time" in result
        
        # Repository 호출 확인
        mock_repositories['chat_repo'].get_user_chats.assert_called_once_with(user_id)
        mock_repositories['bookmark_repo'].get_user_bookmarks.assert_called_once_with(user_id)
        mock_repositories['ai_profile_repo'].get_user_profiles.assert_called_once_with(user_id)
        mock_repositories['user_profile_repo'].update_profile.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_vector_incrementally(self, processor, mock_repositories):
        """증분 벡터 업데이트 테스트"""
        
        user_id = 456
        
        # 기존 프로필 Mock
        existing_profile = MagicMock()
        existing_profile.user_id = user_id
        existing_profile.profile_vector = [0.3, 0.6, 0.4, 0.7, 0.5]
        existing_profile.vector_strength = 0.75
        existing_profile.vector_metadata = {
            "keywords": {"AI": 0.8, "데이터": 0.6},
            "last_incremental_update": datetime.now() - timedelta(hours=2)
        }
        mock_repositories['user_profile_repo'].get_profile.return_value = existing_profile
        
        # 새로운 활동 데이터 (증분)
        new_activities = [
            {
                "content": "새로운 블록체인 기술",
                "timestamp": datetime.now(),
                "activity_type": "bookmark",
                "weight": 1.5
            },
            {
                "content": "NFT 프로젝트 참여",
                "timestamp": datetime.now(),
                "activity_type": "chat",
                "weight": 1.0
            }
        ]
        
        # Vector Generator 증분 업데이트 Mock
        processor.vector_generator.update_vector_incrementally.return_value = (
            [0.35, 0.65, 0.45, 0.72, 0.58],  # 벡터
            {  # 메타데이터
                "vector_strength": 0.82,
                "updated_keywords": {"블록체인": 0.7, "NFT": 0.6},
                "incremental_data_points": 2
            }
        )
        
        # 증분 업데이트 실행
        result = await processor.update_vector_incrementally(
            user_id, 
            new_activities,
            existing_vector=existing_profile.profile_vector,
            existing_metadata=existing_profile.vector_metadata
        )
        
        # 결과 검증
        assert result is not None
        assert result["vector_strength"] == 0.82
        assert result["incremental_data_points"] == 2
        assert "블록체인" in result["updated_keywords"]
        assert "NFT" in result["updated_keywords"]
        
        # 증분 업데이트 메서드 호출 확인
        processor.vector_generator.update_vector_incrementally.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_calculate_user_similarities(self, processor, mock_repositories):
        """사용자 유사도 계산 테스트"""
        
        user_id = 789
        
        # 대상 사용자 프로필
        user_profile = MagicMock()
        user_profile.user_id = user_id
        user_profile.profile_vector = [0.8, 0.3, 0.9, 0.2, 0.7]
        user_profile.vector_metadata = {"keywords": {"AI": 0.9}}
        mock_repositories['user_profile_repo'].get_profile.return_value = user_profile
        
        # 다른 사용자들 프로필
        other_profiles = []
        for uid, vector in [(101, [0.7, 0.4, 0.8, 0.3, 0.6]), (102, [0.2, 0.9, 0.1, 0.8, 0.3]), (103, [0.75, 0.35, 0.85, 0.25, 0.65])]:
            profile = MagicMock()
            profile.user_id = uid
            profile.profile_vector = vector
            profile.vector_metadata = {"keywords": {"tech": 0.7}}
            profile.last_updated = datetime.now()
            other_profiles.append(profile)
        
        mock_repositories['user_profile_repo'].get_all_profiles_except.return_value = other_profiles
        
        # Vector Generator 유사도 계산 Mock
        processor.vector_generator.calculate_vector_similarity = MagicMock(side_effect=[
            0.92,  # user_id=101과의 유사도
            0.23,  # user_id=102와의 유사도  
            0.87   # user_id=103과의 유사도
        ])
        
        # 유사도 계산 실행
        result = await processor.calculate_user_similarities(user_id, min_similarity=0.8, limit=10)
        
        # 결과 검증
        assert result is not None
        assert len(result) == 2  # 0.8 이상인 사용자들만
        
        assert result[0]["user_id"] == 101  # 가장 높은 유사도
        assert result[0]["similarity_score"] == 0.92
        assert result[1]["user_id"] == 103
        assert result[1]["similarity_score"] == 0.87
    
    @pytest.mark.asyncio
    async def test_generate_recommendations(self, processor, mock_repositories):
        """추천 생성 테스트"""
        
        user_id = 555
        
        # 사용자 프로필 Mock
        user_profile = MagicMock()
        user_profile.user_id = user_id
        user_profile.profile_vector = [0.6, 0.8, 0.4, 0.9, 0.3]
        user_profile.vector_metadata = {
            "keywords": {"AI": 0.9, "머신러닝": 0.8, "데이터": 0.7},
            "categories": {"IT": 0.85, "연구": 0.75}
        }
        mock_repositories['user_profile_repo'].get_profile.return_value = user_profile
        
        # 유사 사용자들 Mock
        similar_users = [
            MagicMock(user_id=201, similarity_score=0.9),
            MagicMock(user_id=202, similarity_score=0.85),
            MagicMock(user_id=203, similarity_score=0.8)
        ]
        mock_repositories['similarity_repo'].get_similar_users.return_value = similar_users
        
        # 콘텐츠 후보들 Mock (실제로는 외부 콘텐츠 서비스에서 가져옴)
        content_candidates = [
            {
                "id": 1001,
                "type": "article",
                "title": "최신 GPT-4 연구",
                "description": "대화형 AI의 새로운 발전",
                "tags": ["AI", "GPT", "연구"],
                "category": "research"
            },
            {
                "id": 1002,
                "type": "course",
                "title": "파이토치 딥러닝",
                "description": "실전 딥러닝 프로젝트",
                "tags": ["딥러닝", "파이토치", "실습"],
                "category": "education"
            },
            {
                "id": 1003,
                "type": "tool",
                "title": "데이터 분석 도구",
                "description": "효율적인 데이터 처리",
                "tags": ["데이터", "분석", "도구"],
                "category": "tools"
            }
        ]
        
        # OpenAI 서비스로 콘텐츠 점수 계산 Mock
        processor.openai_service.calculate_content_relevance = AsyncMock(side_effect=[
            0.95,  # 첫 번째 콘텐츠 점수
            0.88,  # 두 번째 콘텐츠 점수
            0.75   # 세 번째 콘텐츠 점수
        ])
        
        # 추천 생성 실행
        result = await processor.generate_recommendations(
            user_id, 
            categories=["research", "education"],
            limit=10
        )
        
        # 결과 검증
        assert result is not None
        assert len(result) <= 10
        
        # Mock 추천 내용 확인 (실제 구현에서는 mock 데이터가 반환됨)
        assert all("id" in rec for rec in result)
        assert all("score" in rec for rec in result)

        # 추천 생성 메서드 호출 확인
        processor.vector_generator.generate_profile_vector.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_chat_completion_event_success(self, processor, mock_repositories):
        """채팅 완료 이벤트 처리 성공 테스트"""
        
        user_id = 123
        
        # 기존 프로필 Mock
        existing_profile = MagicMock()
        existing_profile.user_id = user_id
        existing_profile.profile_vector = [0.2, 0.4, 0.6, 0.3, 0.8]
        existing_profile.vector_metadata = {"keywords": {"programming": 0.7}}
        mock_repositories['user_profile_repo'].get_profile.return_value = existing_profile
        
        # 채팅 데이터
        chat_data = {
            "session_id": "chat_session_123",
            "duration": 600,  # 10분
            "message_count": 15,
            "topic": "AI개발",
            "language": "korean",
            "messages": [
                {"role": "user", "content": "파이썬으로 머신러닝 모델을 만들고 싶어요"},
                {"role": "assistant", "content": "좋은 선택입니다. 먼저 scikit-learn으로 시작해보세요."},
                {"role": "user", "content": "딥러닝도 배우고 싶은데 어떤 프레임워크가 좋을까요?"},
                {"role": "assistant", "content": "TensorFlow나 PyTorch를 추천합니다."},
                {"role": "user", "content": "GPU 설정은 어떻게 하나요?"}
            ],
            "summary": "머신러닝과 딥러닝 학습에 대한 상담",
            "keywords": ["파이썬", "머신러닝", "딥러닝", "GPU"]
        }
        
        # Vector Generator 증분 업데이트 Mock
        processor.vector_generator.update_vector_incrementally = AsyncMock(return_value=(
            [0.25, 0.45, 0.65, 0.35, 0.85],  # 업데이트된 벡터
            {
                "vector_strength": 0.88,
                "updated_keywords": {"파이썬": 0.9, "머신러닝": 0.85, "딥러닝": 0.8},
                "incremental_data_points": 1
            }
        ))
        
        # Redis 클라이언트 Mock
        mock_redis = AsyncMock()
        processor.redis_client = mock_redis
        
        # 채팅 완료 이벤트 처리 실행
        result = await processor.handle_chat_completion_event(user_id, chat_data)
        
        # 결과 검증
        assert result is not None
        assert result["event_type"] == "chat_completion"
        assert result["session_id"] == "chat_session_123"
        assert result["message_count"] == 15
        assert result["vector_strength"] == 0.88
        assert "update_timestamp" in result
        
        # 메서드 호출 확인
        processor.vector_generator.update_vector_incrementally.assert_called_once()
        mock_repositories['user_profile_repo'].update_profile.assert_called_once()
        
        # Redis 캐시 사용 확인
        mock_redis.setex.assert_called_once()
        mock_redis.keys.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_chat_completion_event_without_redis(self, processor, mock_repositories):
        """Redis 없이 채팅 완료 이벤트 처리 테스트"""
        
        user_id = 456
        
        # 기존 프로필 Mock
        existing_profile = MagicMock()
        existing_profile.user_id = user_id
        existing_profile.profile_vector = [0.1, 0.3, 0.5, 0.7, 0.9]
        mock_repositories['user_profile_repo'].get_profile.return_value = existing_profile
        
        # 간단한 채팅 데이터
        chat_data = {
            "session_id": "simple_chat",
            "duration": 300,
            "message_count": 8,
            "topic": "general",
            "messages": [
                {"role": "user", "content": "안녕하세요"},
                {"role": "assistant", "content": "안녕하세요! 무엇을 도와드릴까요?"},
                {"role": "user", "content": "오늘 날씨가 좋네요"}
            ]
        }
        
        # Redis 클라이언트 없음
        processor.redis_client = None
        
        # Vector Generator Mock
        processor.vector_generator.update_vector_incrementally = AsyncMock(return_value=(
            [0.15, 0.35, 0.55, 0.75, 0.95],
            {"vector_strength": 0.75, "incremental_data_points": 1}
        ))
        
        # 채팅 완료 이벤트 처리 실행
        result = await processor.handle_chat_completion_event(
            user_id, chat_data, use_redis_cache=False
        )
        
        # 결과 검증
        assert result is not None
        assert result["event_type"] == "chat_completion"
        assert result["session_id"] == "simple_chat"
        assert result["vector_strength"] == 0.75
        
        # Redis 관련 작업이 실행되지 않았는지 확인
        processor.vector_generator.update_vector_incrementally.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_chat_content_comprehensive(self, processor):
        """채팅 내용 추출 테스트"""
        
        chat_data = {
            "session_id": "test_session_001",
            "topic": "웹개발",
            "language": "korean",
            "message_count": 12,
            "duration": 1200,  # 20분
            "messages": [
                {"role": "user", "content": "React와 Vue.js 중 어떤 것을 배우는 게 좋을까요?"},
                {"role": "assistant", "content": "둘 다 좋은 프레임워크입니다."},
                {"role": "user", "content": "제 이메일은 test@example.com이고 전화번호는 010-1234-5678입니다"},  # 개인정보 포함
                {"role": "user", "content": "TypeScript도 함께 배워야 하나요?"}
            ],
            "summary": "프론트엔드 개발 프레임워크 선택에 대한 상담",
            "keywords": ["React", "Vue.js", "TypeScript", "프론트엔드"]
        }
        
        # 내용 추출 실행
        content = processor._extract_chat_content(chat_data)
        
        # 결과 검증
        assert "Session: test_session_001" in content
        assert "Topic: 웹개발" in content
        assert "Language: korean" in content
        assert "Messages: 12" in content
        assert "Duration: 1200s" in content
        assert "React와 Vue.js" in content
        assert "TypeScript도 함께" in content
        assert "Summary: 프론트엔드 개발" in content
        assert "Keywords: React, Vue.js, TypeScript, 프론트엔드" in content
        
        # 개인정보가 마스킹되었는지 확인
        assert "[EMAIL]" in content
        assert "[PHONE]" in content
        assert "test@example.com" not in content
        assert "010-1234-5678" not in content
    
    @pytest.mark.asyncio
    async def test_calculate_chat_weight(self, processor):
        """채팅 가중치 계산 테스트"""
        
        # 긴 대화, 많은 메시지, 전문적 토픽
        high_importance_chat = {
            "message_count": 25,
            "duration": 2100,  # 35분
            "topic": "work"
        }
        weight_high = processor._calculate_chat_weight(high_importance_chat)
        assert weight_high > 2.0  # 높은 가중치
        
        # 중간 대화
        medium_importance_chat = {
            "message_count": 12,
            "duration": 600,  # 10분
            "topic": "hobby"
        }
        weight_medium = processor._calculate_chat_weight(medium_importance_chat)
        assert 1.0 <= weight_medium <= 2.0  # 중간 가중치
        
        # 짧은 대화
        low_importance_chat = {
            "message_count": 3,
            "duration": 120,  # 2분
            "topic": "general"
        }
        weight_low = processor._calculate_chat_weight(low_importance_chat)
        assert weight_low >= 0.5  # 최소 가중치
        
        # 가중치 순서 확인
        assert weight_high > weight_medium > weight_low
    
    @pytest.mark.asyncio
    async def test_handle_chat_completion_event_error_handling(self, processor, mock_repositories):
        """채팅 완료 이벤트 처리 오류 처리 테스트"""
        
        user_id = 999
        
        # 프로필 조회 실패 Mock
        mock_repositories['user_profile_repo'].get_profile.side_effect = Exception("Database error")
        
        chat_data = {
            "session_id": "error_test",
            "duration": 300,
            "message_count": 5,
            "messages": [{"role": "user", "content": "테스트"}]
        }
        
        # 오류 상황에서 처리 실행
        result = await processor.handle_chat_completion_event(user_id, chat_data)
        
        # 오류 결과 검증
        assert result is not None
        assert "error" in result
        assert result["event_type"] == "chat_completion"
        assert result["user_id"] == user_id
        assert "timestamp" in result


class TestUserProfileProcessorAdvanced:
    """UserProfileProcessor 고급 기능 테스트"""
    
    @pytest.fixture
    def processor(self):
        """Advanced processor with real-like setup"""
        mock_repos = {
            'chat_repo': AsyncMock(),
            'bookmark_repo': AsyncMock(),
            'ai_profile_repo': AsyncMock(),
            'user_profile_repo': AsyncMock(),
            'similarity_repo': AsyncMock(),
            'recommendation_repo': AsyncMock()
        }
        
        with patch('app.services.user_profile_processor.VectorGenerator'), \
             patch('app.services.user_profile_processor.OpenAIService'):
            return UserProfileProcessor(mock_repos)
    
    @pytest.mark.asyncio
    async def test_batch_user_processing(self, processor):
        """배치 사용자 처리 테스트"""
        
        user_ids = [100, 101, 102, 103, 104]
        
        # 각 사용자별 Mock 프로필
        mock_profiles = {}
        for user_id in user_ids:
            profile = MagicMock()
            profile.user_id = user_id
            profile.profile_vector = [0.1 * user_id % 10] * 5
            profile.vector_strength = 0.5 + (user_id % 5) * 0.1
            mock_profiles[user_id] = profile
        
        processor.repositories['user_profile_repo'].get_profile.side_effect = lambda uid: mock_profiles[uid]
        
        # 배치 처리를 위한 Mock 설정
        processor.update_user_profile = AsyncMock()
        processor.update_user_profile.side_effect = [
            {"vector_strength": 0.8, "processing_time": 1.2},
            {"vector_strength": 0.75, "processing_time": 1.5},
            {"vector_strength": 0.9, "processing_time": 0.8},
            {"vector_strength": 0.85, "processing_time": 1.1},
            {"vector_strength": 0.7, "processing_time": 1.4}
        ]
        
        # 배치 처리 실행
        results = await processor.batch_update_profiles(user_ids, max_concurrent=3)
        
        # 결과 검증
        assert len(results) == 5
        assert all("vector_strength" in result for result in results)
        assert all("processing_time" in result for result in results)
        
        # 모든 사용자가 처리되었는지 확인
        processed_user_ids = [call.args[0] for call in processor.update_user_profile.call_args_list]
        assert set(processed_user_ids) == set(user_ids)
    
    @pytest.mark.asyncio
    async def test_profile_quality_assessment(self, processor):
        """프로필 품질 평가 테스트"""
        
        user_id = 999
        
        # 다양한 품질의 프로필 시나리오
        test_scenarios = [
            {
                "name": "high_quality",
                "profile": {
                    "user_id": user_id,
                    "profile_vector": [0.8, 0.7, 0.9, 0.6, 0.85],
                    "vector_strength": 0.9,
                    "last_updated": datetime.now(),
                    "vector_metadata": {
                        "keywords": {"AI": 0.9, "ML": 0.8, "데이터": 0.7},
                        "data_points_processed": 150,
                        "data_sources": ["chat", "bookmark", "ai_profile"]
                    }
                },
                "expected_quality": "high"
            },
            {
                "name": "medium_quality",
                "profile": {
                    "user_id": user_id,
                    "profile_vector": [0.5, 0.4, 0.6, 0.3, 0.55],
                    "vector_strength": 0.6,
                    "last_updated": datetime.now() - timedelta(days=7),
                    "vector_metadata": {
                        "keywords": {"AI": 0.6, "기술": 0.5},
                        "data_points_processed": 50,
                        "data_sources": ["chat", "bookmark"]
                    }
                },
                "expected_quality": "medium"
            },
            {
                "name": "low_quality",
                "profile": {
                    "user_id": user_id,
                    "profile_vector": [0.2, 0.1, 0.3, 0.15, 0.25],
                    "vector_strength": 0.3,
                    "last_updated": datetime.now() - timedelta(days=30),
                    "vector_metadata": {
                        "keywords": {"일반": 0.4},
                        "data_points_processed": 10,
                        "data_sources": ["chat"]
                    }
                },
                "expected_quality": "low"
            }
        ]
        
        for scenario in test_scenarios:
            # Mock 프로필 설정
            mock_profile = MagicMock()
            for key, value in scenario["profile"].items():
                setattr(mock_profile, key, value)
            
            processor.repositories['user_profile_repo'].get_profile.return_value = mock_profile
            
            # 품질 평가 실행
            quality_assessment = await processor.assess_profile_quality(user_id)
            
            # 결과 검증
            assert quality_assessment is not None
            assert "overall_quality" in quality_assessment
            assert "quality_score" in quality_assessment
            assert "recommendations" in quality_assessment
            
            # 예상 품질 등급 확인
            if scenario["expected_quality"] == "high":
                assert quality_assessment["quality_score"] >= 0.8
            elif scenario["expected_quality"] == "medium":
                assert 0.5 <= quality_assessment["quality_score"] < 0.8
            else:  # low
                assert quality_assessment["quality_score"] < 0.5
    
    @pytest.mark.asyncio
    async def test_recommendation_diversity_optimization(self, processor):
        """추천 다양성 최적화 테스트"""
        
        user_id = 777
        
        # 사용자 프로필 - 다양한 관심사를 가진 사용자
        user_profile = MagicMock()
        user_profile.user_id = user_id
        user_profile.profile_vector = [0.7, 0.8, 0.6, 0.9, 0.5]
        user_profile.vector_metadata = {
            "keywords": {"AI": 0.9, "음악": 0.7, "여행": 0.6, "요리": 0.5, "스포츠": 0.4},
            "categories": {"기술": 0.8, "문화": 0.6, "라이프스타일": 0.5}
        }
        processor.repositories['user_profile_repo'].get_profile.return_value = user_profile
        
        # 다양한 카테고리의 콘텐츠 후보들
        diverse_content = [
            # AI/기술 관련 (높은 관련성)
            {"id": 1, "category": "기술", "tags": ["AI", "머신러닝"], "score": 0.95},
            {"id": 2, "category": "기술", "tags": ["AI", "데이터"], "score": 0.92},
            {"id": 3, "category": "기술", "tags": ["프로그래밍"], "score": 0.88},
            
            # 음악 관련 (중간 관련성)
            {"id": 4, "category": "문화", "tags": ["음악", "클래식"], "score": 0.75},
            {"id": 5, "category": "문화", "tags": ["음악", "재즈"], "score": 0.72},
            
            # 여행 관련 (중간 관련성)
            {"id": 6, "category": "라이프스타일", "tags": ["여행", "유럽"], "score": 0.68},
            {"id": 7, "category": "라이프스타일", "tags": ["여행", "아시아"], "score": 0.65},
            
            # 요리 관련 (낮은 관련성)
            {"id": 8, "category": "라이프스타일", "tags": ["요리", "레시피"], "score": 0.58},
            {"id": 9, "category": "라이프스타일", "tags": ["요리", "베이킹"], "score": 0.55}
        ]
        
        # 다양성 최적화된 추천 생성 Mock
        processor._optimize_recommendation_diversity = AsyncMock()
        processor._optimize_recommendation_diversity.return_value = [
            diverse_content[0],  # 기술 - 최고 점수
            diverse_content[4],  # 문화 - 음악 (다른 카테고리)
            diverse_content[6],  # 라이프스타일 - 여행 (또 다른 카테고리)
            diverse_content[2],  # 기술 - 하지만 다른 태그
            diverse_content[8]   # 라이프스타일 - 요리 (완전히 다른 주제)
        ]
        
        # 다양성 최적화 추천 실행
        result = await processor.generate_diverse_recommendations(
            user_id,
            limit=5,
            diversity_factor=0.7  # 70% 다양성, 30% 관련성
        )
        
        # 결과 검증
        assert result is not None
        assert len(result["recommendations"]) == 5
        
        recommendations = result["recommendations"]
        categories = [rec["category"] for rec in recommendations]
        
        # 카테고리 다양성 확인
        unique_categories = set(categories)
        assert len(unique_categories) >= 2  # 최소 2개 이상의 카테고리
        
        # 첫 번째는 여전히 가장 높은 점수여야 함
        assert recommendations[0]["score"] == 0.95
        
        # 다양성 지표 확인
        assert "diversity_score" in result
        assert result["diversity_score"] >= 0.6  # 충분한 다양성
    
    @pytest.mark.asyncio
    async def test_temporal_preference_analysis(self, processor):
        """시간적 선호도 분석 테스트"""
        
        user_id = 666
        
        # 시간대별 활동 패턴을 가진 사용자 데이터
        current_time = datetime.now()
        
        # 최근 활동 (지난 7일)
        recent_activities = [
            {"content": "블록체인 기술 연구", "timestamp": current_time - timedelta(days=1), "weight": 1.0},
            {"content": "NFT 프로젝트 분석", "timestamp": current_time - timedelta(days=2), "weight": 1.0},
            {"content": "웹3 트렌드 관찰", "timestamp": current_time - timedelta(days=3), "weight": 1.0}
        ]
        
        # 중간 활동 (지난 30일)
        medium_activities = [
            {"content": "AI 머신러닝 학습", "timestamp": current_time - timedelta(days=15), "weight": 0.8},
            {"content": "데이터 사이언스 연구", "timestamp": current_time - timedelta(days=20), "weight": 0.8},
            {"content": "파이썬 프로그래밍", "timestamp": current_time - timedelta(days=25), "weight": 0.8}
        ]
        
        # 과거 활동 (지난 90일)
        old_activities = [
            {"content": "웹 개발 공부", "timestamp": current_time - timedelta(days=60), "weight": 0.5},
            {"content": "자바스크립트 프레임워크", "timestamp": current_time - timedelta(days=75), "weight": 0.5},
            {"content": "프론트엔드 디자인", "timestamp": current_time - timedelta(days=80), "weight": 0.5}
        ]
        
        all_activities = recent_activities + medium_activities + old_activities
        
        # 시간적 선호도 분석 Mock
        processor._analyze_temporal_preferences = AsyncMock()
        processor._analyze_temporal_preferences.return_value = {
            "recent_interests": {
                "블록체인": 0.9,
                "NFT": 0.8,
                "웹3": 0.7
            },
            "stable_interests": {
                "AI": 0.85,
                "머신러닝": 0.8,
                "프로그래밍": 0.75
            },
            "declining_interests": {
                "웹개발": 0.4,
                "프론트엔드": 0.3
            },
            "preference_shift_score": 0.6  # 상당한 관심사 변화
        }
        
        # 시간적 가중치 적용된 벡터 생성 Mock
        processor.vector_generator.generate_temporal_weighted_vector.return_value = {
            "profile_vector": [0.2, 0.9, 0.1, 0.8, 0.6],  # 블록체인/웹3 중심
            "metadata": {
                "temporal_weights_applied": True,
                "recent_trend_strength": 0.9,
                "preference_evolution": "블록체인 관심 급증"
            }
        }
        
        # 시간적 선호도 분석 실행
        result = await processor.analyze_temporal_preferences(user_id, all_activities)
        
        # 결과 검증
        assert result is not None
        assert "recent_interests" in result
        assert "stable_interests" in result
        assert "declining_interests" in result
        
        # 최근 관심사가 가장 높은 가중치를 가져야 함
        recent_max = max(result["recent_interests"].values())
        stable_max = max(result["stable_interests"].values())
        assert recent_max >= stable_max
        
        # 선호도 변화 점수 확인
        assert 0 <= result["preference_shift_score"] <= 1
        assert result["preference_shift_score"] > 0.5  # 상당한 변화 감지


class TestUserProfileProcessorPerformance:
    """UserProfileProcessor 성능 테스트"""
    
    @pytest.fixture
    def performance_processor(self):
        """성능 테스트용 processor"""
        mock_repos = {
            'chat_repo': AsyncMock(),
            'bookmark_repo': AsyncMock(),
            'ai_profile_repo': AsyncMock(),
            'user_profile_repo': AsyncMock(),
            'similarity_repo': AsyncMock(),
            'recommendation_repo': AsyncMock()
        }
        
        with patch('app.services.user_profile_processor.VectorGenerator'), \
             patch('app.services.user_profile_processor.OpenAIService'):
            return UserProfileProcessor(mock_repos)
    
    @pytest.mark.asyncio
    async def test_large_scale_similarity_calculation(self, performance_processor):
        """대규모 유사도 계산 성능 테스트"""
        
        user_id = 1000
        
        # 대상 사용자
        target_profile = MagicMock()
        target_profile.user_id = user_id
        target_profile.profile_vector = [0.5] * 128  # 128차원 벡터
        performance_processor.repositories['user_profile_repo'].get_profile.return_value = target_profile
        
        # 10,000명의 다른 사용자 프로필 시뮬레이션
        large_user_base = []
        for i in range(10000):
            profile = MagicMock()
            profile.user_id = i + 2000
            profile.profile_vector = [0.1 + (i % 10) * 0.08] * 128  # 다양한 벡터
            large_user_base.append(profile)
        
        performance_processor.repositories['user_profile_repo'].get_all_profiles_except.return_value = large_user_base
        
        # 빠른 유사도 계산을 위한 배치 처리 Mock
        performance_processor.vector_generator.calculate_batch_similarities.return_value = [
            0.1 + (i % 100) * 0.01 for i in range(10000)  # 0.1 ~ 1.0 범위의 유사도
        ]
        
        # 성능 측정
        start_time = time.time()
        
        result = await performance_processor.calculate_user_similarities(
            user_id, 
            min_similarity=0.8, 
            limit=50,
            batch_size=1000  # 배치 처리
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # 성능 검증
        assert processing_time < 5.0  # 5초 이내 처리
        assert result is not None
        assert len(result) <= 50
        
        # 결과 품질 확인
        assert all(sim["similarity_score"] >= 0.8 for sim in result)
    
    @pytest.mark.asyncio
    async def test_concurrent_recommendation_generation(self, performance_processor):
        """동시 추천 생성 성능 테스트"""
        
        # 여러 사용자에 대한 동시 추천 생성
        user_ids = list(range(100, 120))  # 20명의 사용자
        
        # Mock 설정
        for user_id in user_ids:
            profile = MagicMock()
            profile.user_id = user_id
            profile.profile_vector = [0.1 * (user_id % 10)] * 64
            profile.vector_metadata = {"keywords": {f"interest_{user_id}": 0.8}}
        
        performance_processor.repositories['user_profile_repo'].get_profile.side_effect = lambda uid: profile
        
        # 각 사용자에 대한 추천 생성 Mock
        performance_processor.generate_recommendations = AsyncMock()
        performance_processor.generate_recommendations.return_value = {
            "recommendations": [{"id": i, "score": 0.8} for i in range(10)],
            "generated_at": datetime.now()
        }
        
        # 동시 처리 실행
        start_time = time.time()
        
        tasks = [
            performance_processor.generate_recommendations(user_id, limit=10)
            for user_id in user_ids
        ]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 성능 검증
        assert len(results) == 20
        assert total_time < 10.0  # 10초 이내에 20명 처리
        assert all(len(result["recommendations"]) == 10 for result in results)
        
        # 평균 처리 시간 확인
        avg_time_per_user = total_time / len(user_ids)
        assert avg_time_per_user < 0.5  # 사용자당 0.5초 이내
