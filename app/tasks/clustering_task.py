"""
클러스터링 작업 스케줄러

이 모듈은 사용자 프로파일 클러스터링을 주기적으로 실행하고
관리하는 Celery 태스크들을 정의합니다.

주요 기능:
- 일일 전체 클러스터링
- 실시간 증분 클러스터링
- 클러스터 품질 모니터링
- 자동 재클러스터링
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from celery import Celery
from celery.utils.log import get_task_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from app.core.celery_worker import celery as celery_app
from app.core.database import get_async_session
from app.core.monitoring import prometheus_metrics
from app.services.clustering_service import ClusteringService, ClusteringConfig
from app.models.clustering import (
    UserCluster, ClusteringJobHistory, ClusterQualityMetrics
)
from app.models.user_profile import UserProfile

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name="clustering.full_clustering")
def full_clustering_task(self, config_override: Optional[Dict[str, Any]] = None):
    """
    전체 클러스터링 작업
    
    Args:
        config_override: 설정 오버라이드 딕셔너리
    
    Returns:
        Dict: 작업 결과
    """
    start_time = time.time()
    
    try:
        # 클러스터링 작업 시작 메트릭
        prometheus_metrics.increment_clustering_operations("full_clustering", "started")
        
        result = asyncio.run(_run_full_clustering(config_override))
        
        # 성공/실패에 따른 메트릭 기록
        duration = time.time() - start_time
        if result.get("status") == "success":
            prometheus_metrics.record_celery_task("full_clustering", "success", duration)
            prometheus_metrics.increment_clustering_operations("full_clustering", "success")
        else:
            prometheus_metrics.record_celery_task("full_clustering", "error", duration)
            prometheus_metrics.increment_clustering_operations("full_clustering", "error")
        
        return result
        
    except Exception as e:
        # 예외 발생 시 메트릭 기록
        duration = time.time() - start_time
        prometheus_metrics.record_celery_task("full_clustering", "error", duration)
        prometheus_metrics.increment_clustering_operations("full_clustering", "error")
        raise


@celery_app.task(bind=True, name="clustering.incremental_clustering")
def incremental_clustering_task(self, new_user_ids: List[int]):
    """
    증분 클러스터링 작업
    
    Args:
        new_user_ids: 새로 추가된 사용자 ID 리스트
    
    Returns:
        Dict: 작업 결과
    """
    return asyncio.run(_run_incremental_clustering(new_user_ids))


@celery_app.task(bind=True, name="clustering.quality_monitoring")
def quality_monitoring_task(self):
    """
    클러스터 품질 모니터링 작업
    
    Returns:
        Dict: 모니터링 결과
    """
    start_time = time.time()
    
    try:
        # 모니터링 작업 시작 메트릭
        prometheus_metrics.increment_clustering_operations("quality_monitoring", "started")
        
        result = asyncio.run(_run_quality_monitoring())
        
        # 성공/실패에 따른 메트릭 기록
        duration = time.time() - start_time
        if result.get("status") == "success":
            prometheus_metrics.record_celery_task("quality_monitoring", "success", duration)
            prometheus_metrics.increment_clustering_operations("quality_monitoring", "success")
        else:
            prometheus_metrics.record_celery_task("quality_monitoring", "error", duration)
            prometheus_metrics.increment_clustering_operations("quality_monitoring", "error")
        
        return result
        
    except Exception as e:
        # 예외 발생 시 메트릭 기록
        duration = time.time() - start_time
        prometheus_metrics.record_celery_task("quality_monitoring", "error", duration)
        prometheus_metrics.increment_clustering_operations("quality_monitoring", "error")
        raise


@celery_app.task(bind=True, name="clustering.auto_reclustering")
def auto_reclustering_task(self):
    """
    자동 재클러스터링 작업
    
    Returns:
        Dict: 작업 결과
    """
    return asyncio.run(_run_auto_reclustering())


@celery_app.task(bind=True, name="clustering.cleanup_old_data")
def cleanup_old_data_task(self, days_to_keep: int = 30):
    """
    오래된 클러스터링 데이터 정리 작업
    
    Args:
        days_to_keep: 보관할 데이터 일수
    
    Returns:
        Dict: 정리 결과
    """
    return asyncio.run(_run_cleanup_old_data(days_to_keep))


async def _run_full_clustering(config_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """전체 클러스터링 실행"""
    
    logger.info("🚀 전체 클러스터링 작업 시작")
    start_time = datetime.utcnow()
    
    try:
        async for session in get_async_session():
            # 설정 생성
            config = ClusteringConfig()
            if config_override:
                for key, value in config_override.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            
            # 클러스터링 서비스 초기화
            clustering_service = ClusteringService(session, config)
            
            # 클러스터링 실행
            result = await clustering_service.perform_clustering(
                job_type="scheduled_full_clustering"
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(f"✅ 전체 클러스터링 완료 - {result.n_clusters}개 클러스터, {len(result.user_ids)}명 처리")
            
            return {
                "status": "success",
                "execution_time": execution_time,
                "clusters_created": result.n_clusters,
                "users_processed": len(result.user_ids),
                "silhouette_score": result.silhouette_score,
                "calinski_harabasz_score": result.calinski_harabasz_score,
                "davies_bouldin_score": result.davies_bouldin_score,
                "cluster_sizes": result.cluster_sizes
            }
    
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"❌ 전체 클러스터링 실패: {str(e)}")
        
        return {
            "status": "failed",
            "execution_time": execution_time,
            "error": str(e)
        }


async def _run_incremental_clustering(new_user_ids: List[int]) -> Dict[str, Any]:
    """증분 클러스터링 실행"""
    
    logger.info(f"🔄 증분 클러스터링 작업 시작 - 새 사용자 {len(new_user_ids)}명")
    start_time = datetime.utcnow()
    
    try:
        async for session in get_async_session():
            clustering_service = ClusteringService(session)
            
            # 기존 클러스터 확인
            existing_clusters_result = await session.execute(
                select(UserCluster).where(UserCluster.is_active == True)
            )
            existing_clusters = existing_clusters_result.scalars().all()
            
            if not existing_clusters:
                logger.warning("기존 클러스터가 없어서 전체 클러스터링을 수행합니다.")
                result = await clustering_service.perform_clustering(
                    job_type="incremental_to_full"
                )
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                return {
                    "status": "success",
                    "mode": "full_clustering",
                    "execution_time": execution_time,
                    "clusters_created": result.n_clusters,
                    "users_processed": len(result.user_ids)
                }
            
            # 증분 클러스터링 실행
            logger.info(f"📊 {len(new_user_ids)}명의 새 사용자에 대해 증분 클러스터링 수행")
            result = await clustering_service.incremental_update(
                new_user_ids=new_user_ids,
                update_centers=True  # 클러스터 중심점도 업데이트
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(f"✅ 증분 클러스터링 완료 - {len(new_user_ids)}명 처리")
            
            return {
                "status": "success",
                "mode": "incremental",
                "execution_time": execution_time,
                "clusters_updated": result.n_clusters,
                "users_processed": len(result.user_ids),
                "existing_clusters": len(existing_clusters),
                "processing_time": result.processing_time
            }
    
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"❌ 증분 클러스터링 실패: {str(e)}")
        
        return {
            "status": "failed",
            "execution_time": execution_time,
            "error": str(e)
        }


async def _run_quality_monitoring() -> Dict[str, Any]:
    """클러스터 품질 모니터링 실행"""
    
    logger.info("📊 클러스터 품질 모니터링 시작")
    start_time = datetime.utcnow()
    
    try:
        async for session in get_async_session():
            # 현재 활성 클러스터 조회
            clusters_result = await session.execute(
                select(UserCluster).where(UserCluster.is_active == True)
            )
            clusters = clusters_result.scalars().all()
            
            if not clusters:
                return {
                    "status": "no_clusters",
                    "message": "활성 클러스터가 없습니다."
                }
            
            # 최근 품질 지표 조회
            latest_metrics_result = await session.execute(
                select(ClusterQualityMetrics)
                .where(ClusterQualityMetrics.cluster_id.is_(None))  # 전체 품질 지표
                .order_by(desc(ClusterQualityMetrics.measured_at))
                .limit(1)
            )
            latest_metrics = latest_metrics_result.scalar_one_or_none()
            
            monitoring_result = {
                "status": "success",
                "monitoring_time": datetime.utcnow().isoformat(),
                "total_clusters": len(clusters),
                "cluster_details": [],
                "quality_assessment": {},
                "recommendations": []
            }
            
            # 클러스터별 상세 정보
            total_users = 0
            for cluster in clusters:
                cluster_info = {
                    "cluster_id": cluster.cluster_id,
                    "cluster_name": cluster.cluster_name,
                    "size": cluster.size,
                    "density": cluster.density,
                    "radius": cluster.radius,
                    "dominant_categories": cluster.dominant_categories or {},
                    "created_at": cluster.created_at.isoformat() if cluster.created_at else None
                }
                monitoring_result["cluster_details"].append(cluster_info)
                total_users += cluster.size or 0
            
            # 전체 품질 평가
            if latest_metrics:
                monitoring_result["quality_assessment"] = {
                    "silhouette_score": latest_metrics.silhouette_score,
                    "calinski_harabasz_score": latest_metrics.calinski_harabasz_score,
                    "davies_bouldin_score": latest_metrics.davies_bouldin_score,
                    "measured_at": latest_metrics.measured_at.isoformat(),
                    "total_users_measured": latest_metrics.total_users_measured
                }
                
                # 품질 기반 권장사항
                recommendations = []
                
                if latest_metrics.silhouette_score < 0.3:
                    recommendations.append({
                        "type": "quality_warning",
                        "message": "실루엣 점수가 낮습니다. 클러스터 수 조정을 고려해보세요.",
                        "priority": "high"
                    })
                
                if latest_metrics.davies_bouldin_score > 2.0:
                    recommendations.append({
                        "type": "quality_warning", 
                        "message": "Davies-Bouldin 점수가 높습니다. 클러스터가 너무 겹칠 수 있습니다.",
                        "priority": "medium"
                    })
                
                monitoring_result["recommendations"] = recommendations
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            monitoring_result["execution_time"] = execution_time
            
            logger.info(f"✅ 품질 모니터링 완료 - {len(clusters)}개 클러스터, {total_users}명 사용자")
            
            return monitoring_result
    
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"❌ 품질 모니터링 실패: {str(e)}")
        
        return {
            "status": "failed",
            "execution_time": execution_time,
            "error": str(e)
        }


async def _run_auto_reclustering() -> Dict[str, Any]:
    """자동 재클러스터링 실행"""
    
    logger.info("🔄 자동 재클러스터링 검토 시작")
    start_time = datetime.utcnow()
    
    try:
        async for session in get_async_session():
            # 품질 모니터링 실행
            monitoring_result = await _run_quality_monitoring()
            
            if monitoring_result["status"] != "success":
                return {
                    "status": "skipped",
                    "reason": "품질 모니터링 실패"
                }
            
            # 재클러스터링 필요성 판단
            should_recluster = False
            reclustering_reasons = []
            
            quality_assessment = monitoring_result.get("quality_assessment", {})
            recommendations = monitoring_result.get("recommendations", [])
            
            # 품질 점수 기반 판단
            if quality_assessment.get("silhouette_score", 1.0) < 0.25:
                should_recluster = True
                reclustering_reasons.append("낮은 실루엣 점수")
            
            if quality_assessment.get("davies_bouldin_score", 0.0) > 2.5:
                should_recluster = True
                reclustering_reasons.append("높은 Davies-Bouldin 점수")
            
            # 권장사항 기반 판단
            high_priority_warnings = [
                rec for rec in recommendations 
                if rec.get("priority") == "high"
            ]
            
            if len(high_priority_warnings) >= 2:
                should_recluster = True
                reclustering_reasons.append("다수의 고우선순위 경고")
            
            # 마지막 클러스터링 시점 확인
            last_clustering_result = await session.execute(
                select(ClusteringJobHistory)
                .where(and_(
                    ClusteringJobHistory.status == "completed",
                    ClusteringJobHistory.job_type.in_(["full_clustering", "scheduled_full_clustering"])
                ))
                .order_by(desc(ClusteringJobHistory.started_at))
                .limit(1)
            )
            last_clustering = last_clustering_result.scalar_one_or_none()
            
            if last_clustering:
                days_since_last = (datetime.utcnow() - last_clustering.started_at).days
                if days_since_last > 7:  # 7일 이상 경과
                    should_recluster = True
                    reclustering_reasons.append("마지막 클러스터링으로부터 7일 이상 경과")
            else:
                should_recluster = True
                reclustering_reasons.append("클러스터링 이력 없음")
            
            if not should_recluster:
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                return {
                    "status": "no_action_needed",
                    "execution_time": execution_time,
                    "quality_assessment": quality_assessment,
                    "message": "재클러스터링이 필요하지 않습니다."
                }
            
            # 재클러스터링 실행
            logger.info(f"재클러스터링 실행 - 이유: {', '.join(reclustering_reasons)}")
            
            clustering_service = ClusteringService(session)
            result = await clustering_service.perform_clustering(
                job_type="auto_reclustering"
            )
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            logger.info(f"✅ 자동 재클러스터링 완료 - {result.n_clusters}개 클러스터")
            
            return {
                "status": "reclustered",
                "execution_time": execution_time,
                "reasons": reclustering_reasons,
                "clusters_created": result.n_clusters,
                "users_processed": len(result.user_ids),
                "new_quality_scores": {
                    "silhouette_score": result.silhouette_score,
                    "calinski_harabasz_score": result.calinski_harabasz_score,
                    "davies_bouldin_score": result.davies_bouldin_score
                }
            }
    
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"❌ 자동 재클러스터링 실패: {str(e)}")
        
        return {
            "status": "failed",
            "execution_time": execution_time,
            "error": str(e)
        }


async def _run_cleanup_old_data(days_to_keep: int) -> Dict[str, Any]:
    """오래된 데이터 정리 실행"""
    
    logger.info(f"🧹 오래된 클러스터링 데이터 정리 시작 - {days_to_keep}일 이전 데이터")
    start_time = datetime.utcnow()
    
    try:
        async for session in get_async_session():
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            cleanup_result = {
                "status": "success",
                "cutoff_date": cutoff_date.isoformat(),
                "deleted_records": {}
            }
            
            # 1. 비활성 클러스터 정리
            inactive_clusters_result = await session.execute(
                select(func.count(UserCluster.id))
                .where(and_(
                    UserCluster.is_active == False,
                    UserCluster.created_at < cutoff_date
                ))
            )
            inactive_clusters_count = inactive_clusters_result.scalar() or 0
            
            if inactive_clusters_count > 0:
                from sqlalchemy import delete
                delete_stmt = delete(UserCluster).where(and_(
                    UserCluster.is_active == False,
                    UserCluster.created_at < cutoff_date
                ))
                await session.execute(delete_stmt)
                cleanup_result["deleted_records"]["inactive_clusters"] = inactive_clusters_count
            
            # 2. 오래된 작업 이력 정리 (성공한 작업만, 실패한 작업은 디버깅용으로 보관)
            old_jobs_result = await session.execute(
                select(func.count(ClusteringJobHistory.id))
                .where(and_(
                    ClusteringJobHistory.status == "completed",
                    ClusteringJobHistory.started_at < cutoff_date
                ))
            )
            old_jobs_count = old_jobs_result.scalar() or 0
            
            if old_jobs_count > 0:
                # 최근 10개는 보관
                keep_jobs_result = await session.execute(
                    select(ClusteringJobHistory.id)
                    .where(ClusteringJobHistory.status == "completed")
                    .order_by(desc(ClusteringJobHistory.started_at))
                    .limit(10)
                )
                keep_job_ids = [row[0] for row in keep_jobs_result.fetchall()]
                
                delete_stmt = delete(ClusteringJobHistory).where(and_(
                    ClusteringJobHistory.status == "completed",
                    ClusteringJobHistory.started_at < cutoff_date,
                    ~ClusteringJobHistory.id.in_(keep_job_ids) if keep_job_ids else True
                ))
                await session.execute(delete_stmt)
                cleanup_result["deleted_records"]["old_job_history"] = max(0, old_jobs_count - len(keep_job_ids))
            
            # 3. 오래된 품질 지표 정리
            old_metrics_result = await session.execute(
                select(func.count(ClusterQualityMetrics.id))
                .where(ClusterQualityMetrics.measured_at < cutoff_date)
            )
            old_metrics_count = old_metrics_result.scalar() or 0
            
            if old_metrics_count > 0:
                # 일주일에 하나씩은 보관 (월간 추세 분석용)
                weekly_cutoff = cutoff_date
                keep_metrics_ids = []
                
                for week_offset in range(0, days_to_keep // 7):
                    week_start = weekly_cutoff - timedelta(days=week_offset * 7)
                    week_end = week_start + timedelta(days=7)
                    
                    weekly_metric_result = await session.execute(
                        select(ClusterQualityMetrics.id)
                        .where(and_(
                            ClusterQualityMetrics.measured_at >= week_start,
                            ClusterQualityMetrics.measured_at < week_end,
                            ClusterQualityMetrics.cluster_id.is_(None)  # 전체 품질 지표만
                        ))
                        .order_by(desc(ClusterQualityMetrics.measured_at))
                        .limit(1)
                    )
                    weekly_metric = weekly_metric_result.scalar_one_or_none()
                    if weekly_metric:
                        keep_metrics_ids.append(weekly_metric)
                
                delete_stmt = delete(ClusterQualityMetrics).where(and_(
                    ClusterQualityMetrics.measured_at < cutoff_date,
                    ~ClusterQualityMetrics.id.in_(keep_metrics_ids) if keep_metrics_ids else True
                ))
                await session.execute(delete_stmt)
                cleanup_result["deleted_records"]["old_quality_metrics"] = max(0, old_metrics_count - len(keep_metrics_ids))
            
            await session.commit()
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            cleanup_result["execution_time"] = execution_time
            
            total_deleted = sum(cleanup_result["deleted_records"].values())
            logger.info(f"✅ 데이터 정리 완료 - {total_deleted}개 레코드 삭제")
            
            return cleanup_result
    
    except Exception as e:
        execution_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"❌ 데이터 정리 실패: {str(e)}")
        
        return {
            "status": "failed",
            "execution_time": execution_time,
            "error": str(e)
        }


# 주기적 작업 스케줄 설정 (선택사항 - celery beat 설정 파일에서도 설정 가능)
def setup_periodic_tasks():
    """주기적 작업 스케줄 설정"""
    
    from celery.schedules import crontab
    
    # 기존 스케줄이 있으면 업데이트, 없으면 새로 생성
    current_schedule = getattr(celery_app.conf, 'beat_schedule', {})
    
    clustering_schedule = {
        # 매일 새벽 2시에 전체 클러스터링
        'daily-full-clustering': {
            'task': 'clustering.full_clustering',
            'schedule': crontab(hour=2, minute=0),
            'args': (),
            'options': {'queue': 'clustering'}
        },
        
        # 매 4시간마다 품질 모니터링
        'clustering-quality-monitoring': {
            'task': 'clustering.quality_monitoring',
            'schedule': crontab(minute=0, hour='*/4'),
            'args': (),
            'options': {'queue': 'monitoring'}
        },
        
        # 매주 일요일 새벽 3시에 자동 재클러스터링 (품질이 낮을 때)
        'weekly-auto-reclustering': {
            'task': 'clustering.auto_reclustering',
            'schedule': crontab(hour=3, minute=0, day_of_week=0),
            'args': (),
            'options': {'queue': 'clustering'}
        },
        
        # 매주 토요일 새벽 4시에 오래된 데이터 정리
        'weekly-cleanup-old-data': {
            'task': 'clustering.cleanup_old_data',
            'schedule': crontab(hour=4, minute=0, day_of_week=6),
            'args': (30,),  # 30일 이전 데이터 정리
            'options': {'queue': 'maintenance'}
        },
    }
    
    # 기존 스케줄과 병합
    current_schedule.update(clustering_schedule)
    celery_app.conf.beat_schedule = current_schedule
    celery_app.conf.timezone = 'UTC'


# 사용자 프로파일 업데이트 시 자동으로 증분 클러스터링 트리거하는 헬퍼 함수
async def trigger_incremental_clustering_if_needed(user_id: int):
    """
    사용자 프로파일 업데이트 시 증분 클러스터링 트리거
    
    Args:
        user_id: 업데이트된 사용자 ID
    """
    try:
        # 배치 처리를 위해 Redis나 메모리에 일시적으로 저장 후
        # 주기적으로 배치로 처리하는 것이 효율적
        # 여기서는 단순히 즉시 처리하는 방식으로 구현
        
        incremental_clustering_task.delay([user_id])
        logger.info(f"사용자 {user_id} 증분 클러스터링 작업 스케줄됨")
        
    except Exception as e:
        logger.error(f"증분 클러스터링 트리거 실패 (사용자 {user_id}): {str(e)}")


if __name__ == "__main__":
    # 개발/테스트용 직접 실행
    import sys
    
    if len(sys.argv) > 1:
        task_name = sys.argv[1]
        
        if task_name == "full":
            result = full_clustering_task()
            print(f"Full clustering result: {result}")
        
        elif task_name == "monitoring":
            result = quality_monitoring_task()
            print(f"Quality monitoring result: {result}")
        
        else:
            print("사용법: python clustering_task.py [full|monitoring]")
    
    else:
        print("사용법: python clustering_task.py [full|monitoring]") 