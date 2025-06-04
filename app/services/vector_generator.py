"""
고급 프로필 벡터 생성 서비스

사용자의 다양한 활동 데이터를 분석하여 정교한 프로필 벡터를 생성합니다.
- 다층적 관심사 분석 (키워드 레벨, 토픽 레벨, 카테고리 레벨)
- 시간적 가중치 적용 (최근 활동에 더 높은 가중치)
- 활동 유형별 가중치 차별화
- 개인화된 벡터 정규화
"""

import json
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from loguru import logger

from app.external.openai_service import OpenAIService


class ActivityType(Enum):
    """활동 유형 분류"""
    CHAT = "chat"
    BOOKMARK = "bookmark"
    AI_PROFILE = "ai_profile"
    SEARCH = "search"
    FEEDBACK = "feedback"


@dataclass
class ActivityData:
    """활동 데이터 구조체"""
    activity_type: ActivityType
    content: str
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


@dataclass
class InterestWeight:
    """관심사 가중치 구조체"""
    keyword_weight: float = 1.0
    topic_weight: float = 1.5
    category_weight: float = 2.0
    recency_factor: float = 1.0
    frequency_factor: float = 1.0


class VectorGenerator:
    """고급 프로필 벡터 생성 클래스"""

    def __init__(self, openai_service: OpenAIService):
        self.openai_service = openai_service

        # 벡터 차원 설정
        self.vector_dimension = 1536  # text-embedding-3-small 차원

        # 활동 유형별 기본 가중치
        self.activity_weights = {
            ActivityType.CHAT: 1.0,
            ActivityType.BOOKMARK: 1.5,
            ActivityType.AI_PROFILE: 1.2,
            ActivityType.SEARCH: 0.8,
            ActivityType.FEEDBACK: 0.5
        }

        # 시간 감쇠 파라미터 (일 단위)
        self.time_decay_half_life = 30  # 30일 반감기

        # 최소 벡터 강도 임계값
        self.min_vector_strength = 0.1

    async def generate_profile_vector(
        self,
        activities: List[ActivityData],
        user_preferences: Optional[Dict] = None
    ) -> Tuple[List[float], Dict[str, Any]]:
        """
        사용자 활동으로부터 정교한 프로필 벡터를 생성합니다.

        Args:
            activities: 사용자 활동 데이터 리스트
            user_preferences: 사용자 선호도 설정

        Returns:
            Tuple[벡터, 메타데이터]
        """
        logger.info(f"🧠 프로필 벡터 생성 시작 - 활동 수: {len(activities)}개")

        if not activities:
            return self._create_default_vector(), {"status": "empty_activities"}

        try:
            # 1. 활동 데이터 전처리 및 분석
            processed_activities = self._preprocess_activities(activities)

            # 2. 다층적 관심사 추출
            interest_layers = await self._extract_multilayer_interests(processed_activities)

            # 3. 시간적 가중치 계산
            temporal_weights = self._calculate_temporal_weights(processed_activities)

            # 4. 관심사별 가중 벡터 생성
            weighted_vectors = await self._generate_weighted_vectors(
                interest_layers, temporal_weights, user_preferences
            )

            # 5. 벡터 융합 및 정규화
            final_vector = self._fuse_and_normalize_vectors(weighted_vectors)

            # 6. 메타데이터 생성
            metadata = self._generate_vector_metadata(
                processed_activities, interest_layers, weighted_vectors
            )

            logger.info(f"✅ 프로필 벡터 생성 완료 - 차원: {len(final_vector)}")
            return final_vector, metadata

        except (ValueError, TypeError) as e:
            logger.error(f"❌ 벡터 생성 중 오류: {e}")
            return self._create_default_vector(), {"status": "error", "error": str(e)}

    def _preprocess_activities(self, activities: List[ActivityData]) -> List[ActivityData]:
        """활동 데이터를 전처리합니다."""
        processed = []

        for activity in activities:
            # 빈 콘텐츠 필터링
            if not activity.content or not activity.content.strip():
                continue

            # 중복 콘텐츠 제거 (간단한 해시 기반)
            content_hash = hash(activity.content.lower().strip())
            if content_hash not in [hash(a.content.lower().strip()) for a in processed]:
                # 활동 유형별 가중치 적용
                activity.weight *= self.activity_weights.get(
                    activity.activity_type, 1.0
                )
                processed.append(activity)

        # 시간순 정렬 (최신순)
        processed.sort(key=lambda x: x.created_at, reverse=True)

        logger.debug(f"📋 활동 전처리 완료 - 원본: {len(activities)}개 → 처리됨: {len(processed)}개")
        return processed

    async def _extract_multilayer_interests(
        self,
        activities: List[ActivityData]
    ) -> Dict[str, Dict[str, float]]:
        """다층적 관심사를 추출합니다."""

        # 활동 유형별로 그룹화
        grouped_activities = {}
        for activity in activities:
            activity_type = activity.activity_type.value
            if activity_type not in grouped_activities:
                grouped_activities[activity_type] = []
            grouped_activities[activity_type].append(activity)

        interest_layers = {
            "keywords": {},
            "topics": {},
            "categories": {},
            "concepts": {}  # 추상적 개념
        }

        # 각 활동 유형별로 관심사 추출
        for activity_type, activity_list in grouped_activities.items():
            layer_interests = await self._extract_interests_from_activities(
                activity_list, activity_type
            )

            # 레이어별 병합
            for layer, interests in layer_interests.items():
                if layer in interest_layers:
                    for interest, weight in interests.items():
                        current_weight = interest_layers[layer].get(interest, 0)
                        interest_layers[layer][interest] = current_weight + weight

        # 상위 관심사만 선택 (각 레이어당 최대 50개)
        for layer, interests in interest_layers.items():
            sorted_interests = sorted(
                interests.items(),
                key=lambda x: x[1],
                reverse=True
            )
            interest_layers[layer] = dict(sorted_interests[:50])

        logger.debug("🔍 다층적 관심사 추출 완료")
        return interest_layers

    async def _extract_interests_from_activities(
        self,
        activities: List[ActivityData],
        activity_type: str
    ) -> Dict[str, Dict[str, float]]:
        """특정 활동 유형에서 관심사를 추출합니다."""

        # 콘텐츠 통합
        combined_content = " ".join([
            activity.content for activity in activities[:20]  # 최근 20개만
        ])

        if not combined_content.strip():
            return {"keywords": {}, "topics": {}, "categories": {}, "concepts": {}}

        try:
            # AI를 사용한 정교한 관심사 분석
            prompt = f"""
            다음 {activity_type} 활동 데이터를 분석하여 사용자의 관심사를 4개 레벨로 추출해주세요:

            데이터: {combined_content[:3000]}

            다음 JSON 형식으로 반환해주세요:
            {{
                "keywords": {{"키워드1": 0.9, "키워드2": 0.8, ...}},  // 구체적 키워드 (최대 20개)
                "topics": {{"주제1": 0.9, "주제2": 0.7, ...}},        // 중간 수준 주제 (최대 15개)
                "categories": {{"카테고리1": 0.8, "카테고리2": 0.6, ...}}, // 넓은 카테고리 (최대 10개)
                "concepts": {{"개념1": 0.7, "개념2": 0.5, ...}}       // 추상적 개념 (최대 8개)
            }}

            가중치는 0.0-1.0 사이로, 해당 관심사의 중요도를 나타냅니다.
            더 구체적이고 빈번한 것일수록 높은 가중치를 부여하세요.
            """

            response = await self.openai_service.generate_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4o-mini",
                temperature=0.2
            )

            try:
                interests = json.loads(response.choices[0].message.content)

                # 활동 가중치 적용
                total_activity_weight = sum(activity.weight for activity in activities)
                weight_multiplier = total_activity_weight / len(activities) if activities else 1.0

                for layer in interests:
                    for interest in interests[layer]:
                        interests[layer][interest] *= weight_multiplier

                return interests

            except json.JSONDecodeError:
                logger.warning(f"JSON 파싱 실패 - {activity_type}")
                return {"keywords": {}, "topics": {}, "categories": {}, "concepts": {}}

        except (ConnectionError, TimeoutError) as e:
            logger.error(f"관심사 추출 실패 - {activity_type}: {e}")
            return {"keywords": {}, "topics": {}, "categories": {}, "concepts": {}}

    def _calculate_temporal_weights(self, activities: List[ActivityData]) -> Dict[str, float]:
        """시간적 가중치를 계산합니다 (최근 활동에 더 높은 가중치)."""
        current_time = datetime.utcnow()
        temporal_weights = {}

        for activity in activities:
            # 시간 차이 계산 (일 단위)
            time_diff_days = (current_time - activity.created_at).days

            # 지수적 감쇠 공식: weight = exp(-ln(2) * time_diff / half_life)
            decay_factor = math.exp(-math.log(2) * time_diff_days / self.time_decay_half_life)

            # 활동별 고유 키 생성
            activity_key = f"{activity.activity_type.value}_{hash(activity.content)}"
            temporal_weights[activity_key] = decay_factor

        logger.debug(f"⏰ 시간적 가중치 계산 완료 - 평균 가중치: {np.mean(list(temporal_weights.values())):.3f}")
        return temporal_weights

    async def _generate_weighted_vectors(
        self,
        interest_layers: Dict[str, Dict[str, float]],
        _temporal_weights: Dict[str, float],  # 현재는 사용하지 않음
        user_preferences: Optional[Dict] = None
    ) -> Dict[str, np.ndarray]:
        """관심사별 가중 벡터를 생성합니다."""

        layer_weights = self._get_layer_weights(user_preferences)
        weighted_vectors = {}

        for layer, interests in interest_layers.items():
            if not interests:
                weighted_vectors[layer] = np.zeros(self.vector_dimension)
                continue

            # 레이어별 임베딩 생성
            layer_text = self._create_layer_embedding_text(interests, layer)

            try:
                # OpenAI 임베딩 생성
                embedding_response = await self.openai_service.create_embedding(
                    text=layer_text,
                    model="text-embedding-3-small"
                )

                base_vector = np.array(embedding_response.data[0].embedding)

                # 관심사 가중치 적용
                interest_strength = sum(interests.values()) / len(interests) if interests else 0
                layer_weight = layer_weights.get(layer, 1.0)

                # 최종 가중 벡터
                weighted_vector = base_vector * interest_strength * layer_weight
                weighted_vectors[layer] = weighted_vector

                logger.debug(f"📊 {layer} 벡터 생성 - 강도: {interest_strength:.3f}")

            except (ConnectionError, TimeoutError) as e:
                logger.error(f"❌ {layer} 벡터 생성 실패: {e}")
                weighted_vectors[layer] = np.zeros(self.vector_dimension)

        return weighted_vectors

    def _get_layer_weights(self, user_preferences: Optional[Dict] = None) -> Dict[str, float]:
        """레이어별 가중치를 계산합니다."""
        layer_weights = {
            "keywords": 1.0,
            "topics": 1.3,
            "categories": 1.6,
            "concepts": 2.0
        }

        # 사용자 선호도에 따른 가중치 조정
        if user_preferences:
            preference_multipliers = user_preferences.get("layer_preferences", {})
            for layer, multiplier in preference_multipliers.items():
                if layer in layer_weights:
                    layer_weights[layer] *= multiplier

        return layer_weights

    def _create_layer_embedding_text(self, interests: Dict[str, float], layer: str) -> str:
        """레이어별 임베딩 텍스트를 생성합니다."""
        if not interests:
            return f"general {layer} interests"

        # 가중치에 따라 관심사 반복
        text_parts = []

        for interest, weight in sorted(interests.items(), key=lambda x: x[1], reverse=True):
            # 가중치에 따라 반복 횟수 결정 (1-5회)
            repetitions = max(1, min(5, int(weight * 5)))
            text_parts.extend([interest] * repetitions)

        # 레이어 타입별 컨텍스트 추가
        layer_context = {
            "keywords": "specific interests and preferences",
            "topics": "subject areas and domains of interest",
            "categories": "broad interest categories and fields",
            "concepts": "abstract concepts and philosophical interests"
        }

        context = layer_context.get(layer, "general interests")
        combined_text = f"{context}: {' '.join(text_parts[:100])}"  # 최대 100개 단어

        return combined_text

    def _fuse_and_normalize_vectors(self, weighted_vectors: Dict[str, np.ndarray]) -> List[float]:
        """가중 벡터들을 융합하고 정규화합니다."""

        # 벡터 융합 (가중 평균)
        fusion_weights = {
            "keywords": 0.3,
            "topics": 0.3,
            "categories": 0.25,
            "concepts": 0.15
        }

        fused_vector = np.zeros(self.vector_dimension)
        total_weight = 0

        for layer, vector in weighted_vectors.items():
            layer_weight = fusion_weights.get(layer, 0.1)
            vector_magnitude = np.linalg.norm(vector)

            if vector_magnitude > self.min_vector_strength:
                fused_vector += vector * layer_weight
                total_weight += layer_weight

        # 정규화
        if total_weight > 0:
            fused_vector /= total_weight

        # L2 정규화
        vector_norm = np.linalg.norm(fused_vector)
        if vector_norm > 0:
            fused_vector = fused_vector / vector_norm

        return fused_vector.tolist()

    def _create_default_vector(self) -> List[float]:
        """기본 벡터를 생성합니다."""
        return [0.0] * self.vector_dimension

    def _generate_vector_metadata(
        self,
        activities: List[ActivityData],
        interest_layers: Dict[str, Dict[str, float]],
        weighted_vectors: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """벡터 메타데이터를 생성합니다."""

        # 활동 분포 계산
        activity_distribution = {}
        for activity in activities:
            activity_type = activity.activity_type.value
            activity_distribution[activity_type] = activity_distribution.get(activity_type, 0) + 1

        # 레이어별 강도 계산
        layer_strengths = {}
        for layer, vector in weighted_vectors.items():
            layer_strengths[layer] = float(np.linalg.norm(vector))

        # 주요 관심사 추출
        top_interests = {}
        for layer, interests in interest_layers.items():
            sorted_interests = sorted(interests.items(), key=lambda x: x[1], reverse=True)
            top_interests[layer] = dict(sorted_interests[:5])

        return {
            "generation_timestamp": datetime.utcnow().isoformat(),
            "total_activities": len(activities),
            "activity_distribution": activity_distribution,
            "layer_strengths": layer_strengths,
            "top_interests": top_interests,
            "vector_dimension": self.vector_dimension,
            "algorithm_version": "v2.0",
            "time_decay_half_life_days": self.time_decay_half_life
        }

    def calculate_vector_similarity(
        self,
        vector1: List[float],
        vector2: List[float],
        similarity_type: str = "cosine"
    ) -> float:
        """두 벡터 간의 유사도를 계산합니다."""

        v1 = np.array(vector1)
        v2 = np.array(vector2)

        # 차원 불일치 검사
        if v1.shape != v2.shape:
            logger.warning(f"벡터 차원 불일치: {v1.shape} vs {v2.shape}")
            return 0.0

        if similarity_type == "cosine":
            # 코사인 유사도
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)

            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0

            return float(dot_product / (norm_v1 * norm_v2))

        if similarity_type == "euclidean":
            # 유클리드 거리 기반 유사도 (0-1 범위로 정규화)
            distance = np.linalg.norm(v1 - v2)
            max_distance = np.sqrt(2)  # 정규화된 벡터의 최대 거리
            return max(0.0, 1.0 - (distance / max_distance))

        if similarity_type == "manhattan":
            # 맨하탄 거리 기반 유사도
            distance = np.sum(np.abs(v1 - v2))
            max_distance = 2.0  # 정규화된 벡터의 최대 맨하탄 거리
            return max(0.0, 1.0 - (distance / max_distance))

        # 기본값: 코사인 유사도
        return self.calculate_vector_similarity(vector1, vector2, "cosine")

    async def update_vector_incrementally(
        self,
        current_vector: List[float],
        new_activities: List[ActivityData],
        learning_rate: float = 0.1
    ) -> Tuple[List[float], Dict[str, Any]]:
        """기존 벡터를 새로운 활동으로 점진적 업데이트합니다."""

        if not new_activities:
            return current_vector, {"status": "no_new_activities"}

        # 새로운 활동으로부터 벡터 생성
        new_vector, _ = await self.generate_profile_vector(new_activities)

        # 점진적 업데이트 (가중 평균)
        current_array = np.array(current_vector)
        new_array = np.array(new_vector)

        updated_vector = (1 - learning_rate) * current_array + learning_rate * new_array

        # 정규화
        norm = np.linalg.norm(updated_vector)
        if norm > 0:
            updated_vector = updated_vector / norm

        metadata = {
            "update_type": "incremental",
            "learning_rate": learning_rate,
            "new_activities_count": len(new_activities),
            "previous_vector_norm": float(np.linalg.norm(current_array)),
            "new_vector_norm": float(np.linalg.norm(new_array)),
            "updated_vector_norm": float(np.linalg.norm(updated_vector)),
            "update_timestamp": datetime.utcnow().isoformat()
        }

        return updated_vector.tolist(), metadata
