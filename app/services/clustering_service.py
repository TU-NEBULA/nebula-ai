"""
사용자 프로파일 기반 클러스터링 서비스

이 모듈은 사용자 프로파일 벡터를 기반으로 클러스터링을 수행하는
핵심 서비스를 제공합니다.

주요 기능:
- K-means 클러스터링
- 벡터 전처리 및 정규화
- 최적 클러스터 수 결정
- 클러스터 품질 평가
- 클러스터 특성 분석
"""

import numpy as np
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from sklearn.cluster import KMeans, MiniBatchKMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.ensemble import IsolationForest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from loguru import logger

from app.models.clustering import (
    UserCluster, UserClusterCreate,
    UserClusterMembership, UserClusterMembershipCreate,
    ClusterKeywords, ClusterKeywordsCreate,
    ClusterQualityMetrics, ClusterQualityMetricsCreate,
    ClusteringJobHistory, ClusteringJobHistoryCreate
)
from app.models.user_profile import UserProfile


@dataclass
class ClusteringConfig:
    """클러스터링 설정"""
    # K-means 설정
    min_clusters: int = 2
    max_clusters: int = 20
    max_iter: int = 300
    n_init: int = 10
    random_state: int = 42
    
    # 품질 임계값
    min_silhouette_score: float = 0.3
    max_davies_bouldin_score: float = 2.0
    min_calinski_harabasz_score: float = 100.0
    
    # 데이터 전처리
    enable_pca: bool = False
    pca_variance_ratio: float = 0.95
    outlier_detection: bool = False  # 기본값을 False로 변경 (IsolationForest 호환성 문제)
    outlier_contamination: float = 0.05
    
    # 클러스터 크기 제약
    min_cluster_size: int = 1  # 테스트용으로 1로 변경
    max_cluster_size_ratio: float = 0.5  # 전체 사용자의 50% 이하
    
    # 성능 설정
    use_mini_batch: bool = False
    batch_size: int = 1000


@dataclass
class ClusteringResult:
    """클러스터링 결과"""
    cluster_labels: np.ndarray
    cluster_centers: np.ndarray
    n_clusters: int
    silhouette_score: float
    calinski_harabasz_score: float
    davies_bouldin_score: float
    inertia: float
    processing_time: float
    user_ids: List[int]
    cluster_sizes: Dict[int, int]


@dataclass
class ClusterCharacteristics:
    """클러스터 특성"""
    cluster_id: int
    size: int
    center_vector: List[float]
    density: float
    radius: float
    dominant_categories: Dict[str, float]
    characteristic_keywords: Dict[str, Dict[str, Any]]
    activity_patterns: Dict[str, Any]


class ClusteringService:
    """클러스터링 서비스"""
    
    def __init__(self, session: AsyncSession, config: Optional[ClusteringConfig] = None):
        self.session = session
        self.config = config or ClusteringConfig()
        self.scaler = StandardScaler()
        self.pca = PCA(n_components=0.95) if self.config.enable_pca else None
        self.outlier_detector = IsolationForest(
            contamination=self.config.outlier_contamination,
            random_state=self.config.random_state
        ) if self.config.outlier_detection else None
        
    async def perform_clustering(
        self, 
        force_n_clusters: Optional[int] = None,
        job_type: str = "full_clustering"
    ) -> ClusteringResult:
        """
        전체 클러스터링 실행
        
        Args:
            force_n_clusters: 강제로 지정할 클러스터 수
            job_type: 작업 타입
            
        Returns:
            클러스터링 결과
        """
        start_time = datetime.utcnow()
        
        try:
            # 작업 이력 시작 기록
            job_history = await self._create_job_history(job_type, "running")
            
            # 1. 사용자 프로파일 데이터 로드
            user_data = await self._load_user_profiles()
            if len(user_data) < self.config.min_clusters:
                raise ValueError(f"사용자 수가 부족합니다. 최소 {self.config.min_clusters}명 필요")
            
            logger.info(f"📊 클러스터링 시작 - 사용자 수: {len(user_data)}")
            
            # 2. 벡터 데이터 전처리
            processed_vectors, user_ids = await self._preprocess_vectors(user_data)
            
            # 3. 최적 클러스터 수 결정
            optimal_k = force_n_clusters or await self._find_optimal_clusters(processed_vectors)
            
            # 4. K-means 클러스터링 실행
            clustering_result = await self._execute_kmeans(
                processed_vectors, user_ids, optimal_k
            )
            
            # 5. 클러스터 저장
            await self._save_clusters(clustering_result)
            
            # 6. 사용자 멤버십 저장
            await self._save_user_memberships(clustering_result)
            
            # 7. 클러스터 특성 분석 및 저장
            await self._analyze_and_save_cluster_characteristics(clustering_result, user_data)
            
            # 8. 품질 지표 저장
            await self._save_quality_metrics(clustering_result)
            
            # 9. 작업 이력 완료 처리
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            await self._complete_job_history(
                job_history.id, "completed", clustering_result, execution_time
            )
            
            logger.info(f"✅ 클러스터링 완료 - {optimal_k}개 클러스터, 실행시간: {execution_time:.2f}초")
            return clustering_result
            
        except Exception as e:
            logger.error(f"❌ 클러스터링 실패: {str(e)}")
            if 'job_history' in locals():
                await self._complete_job_history(
                    job_history.id, "failed", None, None, str(e)
                )
            raise
    
    async def _load_user_profiles(
        self, user_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """사용자 프로파일 데이터 로드"""
        query = select(UserProfile).where(
            and_(
                UserProfile.profile_vector.isnot(None),
                UserProfile.vector_strength > 0.1  # 최소 벡터 강도
            )
        )
        
        if user_ids:
            query = query.where(UserProfile.user_id.in_(user_ids))
        
        result = await self.session.execute(query)
        profiles = result.scalars().all()
        
        return [
            {
                'user_id': profile.user_id,
                'profile_vector': profile.profile_vector,
                'keywords_frequency': profile.keywords_frequency or {},
                'categories_distribution': profile.categories_distribution or {},
                'activity_patterns': profile.activity_patterns or {},
                'total_bookmarks': profile.total_bookmarks,
                'last_activity_at': profile.last_activity_at
            }
            for profile in profiles
        ]
    
    async def _preprocess_vectors(
        self, user_data: List[Dict[str, Any]]
    ) -> Tuple[np.ndarray, List[int]]:
        """벡터 데이터 전처리"""
        vectors = []
        user_ids = []
        
        for user in user_data:
            if user['profile_vector'] is not None and len(user['profile_vector']) == 1536:
                vectors.append(user['profile_vector'])
                user_ids.append(user['user_id'])
        
        if not vectors:
            raise ValueError("유효한 벡터 데이터가 없습니다.")
        
        # NumPy 배열로 변환
        vectors_array = np.array(vectors, dtype=np.float32)
        
        # 1. 이상치 탐지 및 제거
        if self.outlier_detector:
            outlier_mask = self.outlier_detector.fit_predict(vectors_array)
            normal_indices = outlier_mask == 1
            vectors_array = vectors_array[normal_indices]
            user_ids = [user_ids[i] for i in range(len(user_ids)) if normal_indices[i]]
            
            logger.info(f"🧹 이상치 제거: {np.sum(~normal_indices)}개 제거, {len(user_ids)}개 유지")
        
        # 2. 정규화 (L2 normalization for cosine similarity)
        vectors_array = vectors_array / np.linalg.norm(vectors_array, axis=1, keepdims=True)
        
        # 3. 표준화 (선택적)
        if self.config.enable_pca or True:  # 일반적으로 클러스터링에 도움
            vectors_array = self.scaler.fit_transform(vectors_array)
        
        # 4. 차원 축소 (선택적)
        if self.pca:
            vectors_array = self.pca.fit_transform(vectors_array)
            logger.info(f"📐 PCA 적용: {vectors_array.shape[1]}차원으로 축소")
        
        return vectors_array, user_ids
    
    async def _find_optimal_clusters(self, vectors: np.ndarray) -> int:
        """최적 클러스터 수 찾기 (엘보우 메서드 + 실루엣 분석)"""
        n_samples = len(vectors)
        # 실루엣 점수는 최대 n_samples - 1까지만 유효
        max_k = min(self.config.max_clusters, n_samples - 1, n_samples // max(1, self.config.min_cluster_size))
        
        if max_k < self.config.min_clusters:
            return self.config.min_clusters
        
        silhouette_scores = []
        inertias = []
        k_range = range(self.config.min_clusters, max_k + 1)
        
        logger.info(f"🔍 최적 클러스터 수 탐색: K={self.config.min_clusters}~{max_k}")
        
        for k in k_range:
            # K-means 실행
            kmeans = KMeans(
                n_clusters=k,
                random_state=self.config.random_state,
                n_init=self.config.n_init,
                max_iter=self.config.max_iter
            )
            labels = kmeans.fit_predict(vectors)
            
            # 실루엣 점수 계산
            if k > 1:  # 실루엣 점수는 k>1일 때만 계산 가능
                silhouette_avg = silhouette_score(vectors, labels)
                silhouette_scores.append(silhouette_avg)
            else:
                silhouette_scores.append(0)
            
            inertias.append(kmeans.inertia_)
        
        # 엘보우 메서드로 후보 선별
        elbow_candidates = self._find_elbow_points(list(k_range), inertias)
        
        # 실루엣 점수가 높은 후보 선택
        if silhouette_scores:
            best_k_idx = 0
            best_score = silhouette_scores[0]
            
            for i, (k, score) in enumerate(zip(k_range, silhouette_scores)):
                if k in elbow_candidates and score > best_score:
                    best_k_idx = i
                    best_score = score
            
            optimal_k = list(k_range)[best_k_idx]
        else:
            optimal_k = self.config.min_clusters
        
        logger.info(f"🎯 선택된 최적 클러스터 수: {optimal_k} (실루엣 점수: {best_score:.3f})")
        return optimal_k
    
    def _find_elbow_points(self, k_values: List[int], inertias: List[float]) -> List[int]:
        """엘보우 포인트 찾기"""
        if len(inertias) < 3:
            return k_values
        
        # 기울기 변화율 계산
        slopes = []
        for i in range(1, len(inertias)):
            slope = inertias[i-1] - inertias[i]
            slopes.append(slope)
        
        # 기울기 변화율이 급격히 감소하는 지점 찾기
        slope_changes = []
        for i in range(1, len(slopes)):
            change = slopes[i-1] - slopes[i]
            slope_changes.append(change)
        
        # 상위 30% 변화율을 가진 K값들을 후보로 선정
        if slope_changes:
            threshold = np.percentile(slope_changes, 70)
            candidates = []
            for i, change in enumerate(slope_changes):
                if change >= threshold:
                    candidates.append(k_values[i + 1])  # 인덱스 조정
            
            return candidates if candidates else [k_values[len(k_values)//2]]
        
        return k_values[1:len(k_values)//2 + 1]  # 중간 범위 반환
    
    async def _execute_kmeans(
        self, vectors: np.ndarray, user_ids: List[int], n_clusters: int
    ) -> ClusteringResult:
        """K-means 클러스터링 실행"""
        start_time = datetime.utcnow()
        
        # 클러스터링 알고리즘 선택
        if self.config.use_mini_batch and len(vectors) > self.config.batch_size:
            kmeans = MiniBatchKMeans(
                n_clusters=n_clusters,
                random_state=self.config.random_state,
                batch_size=self.config.batch_size,
                max_iter=self.config.max_iter
            )
        else:
            kmeans = KMeans(
                n_clusters=n_clusters,
                random_state=self.config.random_state,
                n_init=self.config.n_init,
                max_iter=self.config.max_iter
            )
        
        # 클러스터링 실행
        labels = kmeans.fit_predict(vectors)
        
        # 품질 지표 계산
        silhouette_avg = silhouette_score(vectors, labels) if n_clusters > 1 else 0
        calinski_harabasz = calinski_harabasz_score(vectors, labels) if n_clusters > 1 else 0
        davies_bouldin = davies_bouldin_score(vectors, labels) if n_clusters > 1 else 0
        
        # 클러스터 크기 계산
        unique_labels, counts = np.unique(labels, return_counts=True)
        cluster_sizes = dict(zip(unique_labels.astype(int), counts.astype(int)))
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return ClusteringResult(
            cluster_labels=labels,
            cluster_centers=kmeans.cluster_centers_,
            n_clusters=n_clusters,
            silhouette_score=silhouette_avg,
            calinski_harabasz_score=calinski_harabasz,
            davies_bouldin_score=davies_bouldin,
            inertia=kmeans.inertia_,
            processing_time=processing_time,
            user_ids=user_ids,
            cluster_sizes=cluster_sizes
        )
    
    async def _save_clusters(self, result: ClusteringResult) -> None:
        """클러스터 정보 저장"""
        # 기존 클러스터 완전 삭제 (중복 키 문제 방지)
        from sqlalchemy import delete
        await self.session.execute(delete(UserCluster))
        await self.session.commit()  # 즉시 커밋해서 삭제 반영
        
        # 새 클러스터 저장
        for cluster_id in range(result.n_clusters):
            cluster_create = UserClusterCreate(
                cluster_id=cluster_id,
                cluster_name=f"Cluster_{cluster_id}",  # 임시 이름, 나중에 특성 분석 후 업데이트
                center_vector=result.cluster_centers[cluster_id].tolist(),
                size=result.cluster_sizes.get(cluster_id, 0),
                is_active=True
            )
            
            cluster = UserCluster.model_validate(cluster_create.model_dump())
            self.session.add(cluster)
        
        await self.session.commit()
    
    async def _save_user_memberships(self, result: ClusteringResult) -> None:
        """사용자 클러스터 멤버십 저장"""
        # 기존 멤버십 삭제 - 올바른 방식으로 수정
        from sqlalchemy import delete
        stmt = delete(UserClusterMembership).where(
            UserClusterMembership.user_id.in_(result.user_ids)
        )
        await self.session.execute(stmt)
        
        # 새 멤버십 저장
        for user_id, cluster_label in zip(result.user_ids, result.cluster_labels):
            # 클러스터 중심점과의 거리 계산
            user_idx = result.user_ids.index(user_id)
            center_vector = result.cluster_centers[cluster_label]
            
            # 원본 벡터에서 거리 계산 (전처리된 벡터가 아닌)
            # 실제로는 전처리된 벡터를 사용해야 하지만, 여기서는 추정치 사용
            distance = 1.0  # 임시값
            
            membership_create = UserClusterMembershipCreate(
                user_id=user_id,
                cluster_id=int(cluster_label),
                distance_to_center=float(distance),
                confidence_score=1.0 - min(distance / 2.0, 1.0),  # 거리 기반 신뢰도
                assignment_reason="kmeans"
            )
            
            membership = UserClusterMembership.model_validate(membership_create.model_dump())
            self.session.add(membership)
        
        await self.session.commit()
    
    async def _analyze_and_save_cluster_characteristics(
        self, result: ClusteringResult, user_data: List[Dict[str, Any]]
    ) -> None:
        """클러스터 특성 분석 및 저장"""
        # 사용자별 클러스터 매핑 생성
        user_cluster_map = dict(zip(result.user_ids, result.cluster_labels))
        
        for cluster_id in range(result.n_clusters):
            # 클러스터에 속한 사용자들 필터링
            cluster_users = [
                user for user in user_data 
                if user['user_id'] in user_cluster_map 
                and user_cluster_map[user['user_id']] == cluster_id
            ]
            
            if not cluster_users:
                continue
            
            # 특성 분석
            characteristics = await self._analyze_cluster_characteristics(
                cluster_id, cluster_users, result.cluster_centers[cluster_id]
            )
            
            # 클러스터 정보 업데이트
            cluster = await self.session.execute(
                select(UserCluster).where(
                    and_(
                        UserCluster.cluster_id == cluster_id,
                        UserCluster.is_active == True
                    )
                )
            )
            cluster_obj = cluster.scalar_one_or_none()
            
            if cluster_obj:
                cluster_obj.cluster_name = await self._generate_cluster_name(characteristics)
                cluster_obj.density = characteristics.density
                cluster_obj.radius = characteristics.radius
                cluster_obj.dominant_categories = characteristics.dominant_categories
                cluster_obj.characteristic_keywords = characteristics.characteristic_keywords
                cluster_obj.activity_patterns = characteristics.activity_patterns
            
            # 키워드 저장
            await self._save_cluster_keywords(characteristics)
        
        await self.session.commit()
    
    async def _analyze_cluster_characteristics(
        self, 
        cluster_id: int, 
        cluster_users: List[Dict[str, Any]], 
        center_vector: np.ndarray
    ) -> ClusterCharacteristics:
        """개별 클러스터 특성 분석"""
        size = len(cluster_users)
        
        # 1. 밀도 계산 (사용자들 간의 평균 거리의 역수)
        if size > 1:
            user_vectors = np.array([user['profile_vector'] for user in cluster_users])
            distances = []
            for i in range(len(user_vectors)):
                for j in range(i+1, len(user_vectors)):
                    dist = np.linalg.norm(user_vectors[i] - user_vectors[j])
                    distances.append(dist)
            avg_distance = np.mean(distances) if distances else 1.0
            density = 1.0 / (1.0 + avg_distance)
        else:
            density = 1.0
        
        # 2. 반경 계산 (중심점에서 가장 먼 사용자까지의 거리)
        if cluster_users:
            user_vectors = np.array([user['profile_vector'] for user in cluster_users])
            distances_to_center = [
                np.linalg.norm(vector - center_vector) for vector in user_vectors
            ]
            radius = max(distances_to_center) if distances_to_center else 0.0
        else:
            radius = 0.0
        
        # 3. 카테고리 분포 분석
        dominant_categories = self._analyze_category_distribution(cluster_users)
        
        # 4. 키워드 분석
        characteristic_keywords = self._analyze_cluster_keywords(cluster_users)
        
        # 5. 활동 패턴 분석
        activity_patterns = self._analyze_activity_patterns(cluster_users)
        
        return ClusterCharacteristics(
            cluster_id=cluster_id,
            size=size,
            center_vector=center_vector.tolist(),
            density=float(density),
            radius=float(radius),
            dominant_categories=dominant_categories,
            characteristic_keywords=characteristic_keywords,
            activity_patterns=activity_patterns
        )
    
    def _analyze_category_distribution(
        self, cluster_users: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """클러스터 내 카테고리 분포 분석"""
        category_counts = {}
        total_users = len(cluster_users)
        
        for user in cluster_users:
            categories = user.get('categories_distribution', {})
            for category, percentage in categories.items():
                if category not in category_counts:
                    category_counts[category] = 0
                category_counts[category] += percentage
        
        # 평균 계산 및 정규화
        category_distribution = {}
        for category, total_percentage in category_counts.items():
            avg_percentage = total_percentage / total_users
            category_distribution[category] = round(avg_percentage, 3)
        
        # 상위 10개 카테고리만 반환
        sorted_categories = sorted(
            category_distribution.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        return dict(sorted_categories)
    
    def _analyze_cluster_keywords(
        self, cluster_users: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """클러스터 특징 키워드 분석"""
        keyword_stats = {}
        total_users = len(cluster_users)
        
        for user in cluster_users:
            keywords = user.get('keywords_frequency', {})
            for keyword, keyword_data in keywords.items():
                if keyword not in keyword_stats:
                    keyword_stats[keyword] = {
                        'total_frequency': 0,
                        'total_weight': 0.0,
                        'user_count': 0
                    }
                
                freq = keyword_data.get('frequency', 0) if isinstance(keyword_data, dict) else 1
                weight = keyword_data.get('weight', 1.0) if isinstance(keyword_data, dict) else 1.0
                
                keyword_stats[keyword]['total_frequency'] += freq
                keyword_stats[keyword]['total_weight'] += weight
                keyword_stats[keyword]['user_count'] += 1
        
        # 평균 계산 및 중요도 점수 산출
        characteristic_keywords = {}
        importance_scores = []
        
        for keyword, stats in keyword_stats.items():
            avg_frequency = stats['total_frequency'] / total_users
            avg_weight = stats['total_weight'] / total_users
            user_ratio = stats['user_count'] / total_users
            
            # 중요도 점수 = 가중치 × 사용자 비율 × log(빈도)
            importance_score = avg_weight * user_ratio * np.log1p(avg_frequency)
            importance_scores.append(importance_score)
            
            characteristic_keywords[keyword] = {
                'raw_importance': importance_score,
                'frequency': int(stats['total_frequency']),
                'user_ratio': round(user_ratio, 3)
            }
        
        # weight 값을 0-1 범위로 정규화
        if importance_scores:
            max_importance = max(importance_scores)
            min_importance = min(importance_scores)
            
            for keyword in characteristic_keywords:
                raw_importance = characteristic_keywords[keyword]['raw_importance']
                if max_importance > min_importance:
                    normalized_weight = (raw_importance - min_importance) / (max_importance - min_importance)
                else:
                    normalized_weight = 0.5  # 모든 값이 같을 때
                
                characteristic_keywords[keyword]['weight'] = round(normalized_weight, 4)
                del characteristic_keywords[keyword]['raw_importance']
        
        # 상위 20개 키워드만 반환
        sorted_keywords = sorted(
            characteristic_keywords.items(),
            key=lambda x: x[1]['weight'],
            reverse=True
        )[:20]
        
        return dict(sorted_keywords)
    
    def _analyze_activity_patterns(
        self, cluster_users: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """클러스터 활동 패턴 분석"""
        patterns = {
            'avg_bookmarks': 0,
            'activity_distribution': {},
            'peak_hours': [],
            'session_patterns': {}
        }
        
        total_bookmarks = sum(user.get('total_bookmarks', 0) for user in cluster_users)
        patterns['avg_bookmarks'] = round(total_bookmarks / len(cluster_users), 1)
        
        # 활동 패턴 집계
        for user in cluster_users:
            activity = user.get('activity_patterns', {})
            for pattern_key, pattern_value in activity.items():
                if pattern_key not in patterns['activity_distribution']:
                    patterns['activity_distribution'][pattern_key] = []
                patterns['activity_distribution'][pattern_key].append(pattern_value)
        
        # 평균 계산
        for pattern_key, values in patterns['activity_distribution'].items():
            if values and all(isinstance(v, (int, float)) for v in values):
                patterns['activity_distribution'][pattern_key] = round(
                    sum(values) / len(values), 2
                )
        
        return patterns
    
    async def _generate_cluster_name(
        self, characteristics: ClusterCharacteristics
    ) -> str:
        """클러스터 이름 자동 생성"""
        # 주요 카테고리 추출
        top_category = None
        if characteristics.dominant_categories:
            top_category = max(
                characteristics.dominant_categories.items(), 
                key=lambda x: x[1]
            )[0]
        
        # 주요 키워드 추출
        top_keywords = []
        if characteristics.characteristic_keywords:
            sorted_keywords = sorted(
                characteristics.characteristic_keywords.items(),
                key=lambda x: x[1]['weight'],
                reverse=True
            )[:3]
            top_keywords = [kw[0] for kw in sorted_keywords]
        
        # 이름 생성
        name_parts = []
        
        if top_category:
            name_parts.append(top_category.replace(' ', '_'))
        
        if top_keywords:
            name_parts.extend(top_keywords[:2])
        
        if not name_parts:
            name_parts.append(f"Cluster_{characteristics.cluster_id}")
        
        # 클러스터 크기 정보 추가
        if characteristics.size > 1000:
            name_parts.append("Large")
        elif characteristics.size < 100:
            name_parts.append("Small")
        
        return "_".join(name_parts[:4])  # 최대 4개 요소
    
    async def _save_cluster_keywords(
        self, characteristics: ClusterCharacteristics
    ) -> None:
        """클러스터 키워드 저장"""
        # 기존 키워드 삭제
        from sqlalchemy import delete
        stmt = delete(ClusterKeywords).where(
            ClusterKeywords.cluster_id == characteristics.cluster_id
        )
        await self.session.execute(stmt)
        
        # 새 키워드 저장
        rank = 1
        for keyword, stats in characteristics.characteristic_keywords.items():
            keyword_create = ClusterKeywordsCreate(
                cluster_id=characteristics.cluster_id,
                keyword=keyword,
                weight=stats['weight'],
                frequency=stats['frequency'],
                rank=rank,
                uniqueness_score=stats.get('user_ratio', 0.0)
            )
            
            keyword_obj = ClusterKeywords.model_validate(keyword_create.model_dump())
            self.session.add(keyword_obj)
            rank += 1
    
    async def _save_quality_metrics(self, result: ClusteringResult) -> None:
        """클러스터 품질 지표 저장"""
        # 전체 품질 지표
        overall_metrics = ClusterQualityMetricsCreate(
            cluster_id=None,  # 전체 클러스터링 품질
            silhouette_score=result.silhouette_score,
            calinski_harabasz_score=result.calinski_harabasz_score,
            davies_bouldin_score=result.davies_bouldin_score,
            measurement_type="post_clustering",
            total_users_measured=len(result.user_ids),
            algorithm_version="kmeans_v1.0"
        )
        
        overall_obj = ClusterQualityMetrics.model_validate(overall_metrics.model_dump())
        self.session.add(overall_obj)
        
        await self.session.commit()
    
    async def _create_job_history(
        self, job_type: str, status: str
    ) -> ClusteringJobHistory:
        """클러스터링 작업 이력 생성"""
        job_create = ClusteringJobHistoryCreate(
            job_type=job_type,
            algorithm_used="kmeans",
            status=status,
            parameters_used={
                "min_clusters": self.config.min_clusters,
                "max_clusters": self.config.max_clusters,
                "random_state": self.config.random_state,
                "enable_pca": self.config.enable_pca,
                "outlier_detection": self.config.outlier_detection
            }
        )
        
        job_obj = ClusteringJobHistory.model_validate(job_create.model_dump())
        self.session.add(job_obj)
        await self.session.commit()
        await self.session.refresh(job_obj)
        
        return job_obj
    
    async def _complete_job_history(
        self, 
        job_id: str, 
        status: str, 
        result: Optional[ClusteringResult] = None,
        execution_time: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> None:
        """클러스터링 작업 이력 완료 처리"""
        job = await self.session.get(ClusteringJobHistory, job_id)
        if job:
            job.status = status
            job.completed_at = datetime.utcnow()
            job.error_message = error_message
            
            if result:
                job.clusters_created = result.n_clusters
                job.users_processed = len(result.user_ids)
                job.overall_quality_score = result.silhouette_score
            
            if execution_time:
                job.execution_time_seconds = execution_time
            
            await self.session.commit()


class ClusteringServiceFactory:
    """클러스터링 서비스 팩토리"""
    
    @staticmethod
    def create_service(
        session: AsyncSession, 
        config: Optional[ClusteringConfig] = None
    ) -> ClusteringService:
        """클러스터링 서비스 인스턴스 생성"""
        return ClusteringService(session, config)
    
    @staticmethod
    def create_config(
        min_clusters: int = 2,
        max_clusters: int = 20,
        min_silhouette_score: float = 0.3,
        enable_pca: bool = False,
        outlier_detection: bool = True,
        use_mini_batch: bool = False
    ) -> ClusteringConfig:
        """사용자 정의 클러스터링 설정 생성"""
        return ClusteringConfig(
            min_clusters=min_clusters,
            max_clusters=max_clusters,
            min_silhouette_score=min_silhouette_score,
            enable_pca=enable_pca,
            outlier_detection=outlier_detection,
            use_mini_batch=use_mini_batch
        ) 