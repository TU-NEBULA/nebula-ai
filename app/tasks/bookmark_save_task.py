"""
북마크 저장 태스크 모듈

이 모듈은 웹 페이지 북마크의 완전한 처리 워크플로우를 담당하는 Celery 태스크를 정의합니다:
1. S3에서 HTML 콘텐츠 다운로드
2. 유사도 계산 및 관계 데이터 생성
3. 관계 메시지 발행 (Spring Boot로 전송)
4. PostgreSQL 벡터 데이터베이스에 저장
5. 사용자 프로필 업데이트 이벤트 트리거

모든 무거운 작업을 백그라운드에서 처리하여 Consumer의 성능을 최적화합니다.
"""

from dataclasses import dataclass
from typing import List, Dict
import asyncio
import logging
import concurrent.futures
from datetime import datetime
import time

from loguru import logger
from app.core.celery_worker import celery
from app.core.database import get_async_session
from app.external.s3_service import download_html_from_s3, download_html_from_url
from app.services.vector_service import vector_service
from app.services.similarity_service import SimilarityService
from app.services.message_publisher import message_publisher
from app.utils.text_processing import extract_main_text, prepare_content_for_rag
from app.utils.async_utils import run_async_safely
from app.tasks.user_profile_tasks import create_repositories
from app.services.vector_generator import ActivityData, ActivityType
from app.services.vector_generator import VectorGenerator
from app.external.openai_service import OpenAIService
from app.core.monitoring import prometheus_metrics

# 서비스 인스턴스들
similarity_service = SimilarityService()

# pylint: disable=too-many-instance-attributes
@dataclass
class BookmarkData:
    """북마크 데이터를 담는 데이터클래스"""
    user_id: int
    star_id: str
    s3_key: str
    title: str
    url: str
    keywords: list
    memo: str
    summary: str


async def _download_and_extract_content(s3_key: str, url: str) -> str:
    """S3에서 HTML을 다운로드하고 텍스트를 추출합니다. S3 실패 시 URL로 fallback합니다."""
    logger.info("📥 콘텐츠 다운로드 시작 - s3_key: {}, url: {}", s3_key, url)
    
    # 1차 시도: S3에서 다운로드
    try:
        logger.info("📥 S3에서 HTML 다운로드 시도 - s3_key: {}", s3_key)
        html = download_html_from_s3(s3_key)
        body_text = extract_main_text(html)
        logger.info("📄 S3에서 텍스트 추출 완료 - 길이: {}", len(body_text))
        return body_text
        
    except FileNotFoundError as e:
        logger.warning("⚠️ S3 파일이 존재하지 않음 - s3_key: {}, URL로 fallback 시도", s3_key)
        
        # 2차 시도: URL에서 직접 다운로드
        try:
            logger.info("🌐 URL에서 HTML 다운로드 시도 - url: {}", url)
            html = download_html_from_url(url)
            body_text = extract_main_text(html)
            logger.warning("⚠️ URL fallback 성공 - url: {}, 텍스트 길이: {}", url, len(body_text))
            return body_text
            
        except (ConnectionError, ValueError) as url_error:
            logger.error("❌ URL fallback도 실패 - url: {}, 오류: {}", url, url_error)
            logger.warning("⚠️ S3와 URL 모두 실패, 빈 콘텐츠로 처리 진행")
            return ""
        
    except (ConnectionError, ValueError) as e:
        logger.error("❌ S3 다운로드 실패 - s3_key: {}, 오류: {}", s3_key, e)
        # S3에 연결 문제가 있는 경우에도 URL로 fallback 시도
        try:
            logger.info("🌐 S3 연결 실패로 URL fallback 시도 - url: {}", url)
            html = download_html_from_url(url)
            body_text = extract_main_text(html)
            logger.warning("⚠️ URL fallback 성공 - url: {}, 텍스트 길이: {}", url, len(body_text))
            return body_text
            
        except (ConnectionError, ValueError) as url_error:
            logger.error("❌ URL fallback도 실패 - url: {}, 오류: {}", url, url_error)
            # 중요한 에러는 재발생시켜 태스크 재시도 유도
            raise
        
    except Exception as e:
        logger.error("❌ 예상치 못한 오류 - s3_key: {}, url: {}, 오류: {}", s3_key, url, e)
        # 예상치 못한 에러도 재발생
        raise


async def _calculate_similarity(bookmark_data: BookmarkData, body_text: str) -> List[Dict]:
    """유사도 계산을 수행합니다."""
    logger.info("🔍 유사도 계산 시작...")
    
    # S3 파일이 없어 body_text가 비어있더라도 메타데이터로 유사도 계산 진행
    if not body_text:
        logger.info("📝 본문 텍스트가 비어있음 - 메타데이터만으로 유사도 계산 진행")
        content_for_similarity = (
            f"{bookmark_data.title} {bookmark_data.summary} "
            f"{' '.join(bookmark_data.keywords)}"
        )
    else:
        content_for_similarity = (
            f"{bookmark_data.title} {bookmark_data.summary} "
            f"{' '.join(bookmark_data.keywords)} {body_text[:1000]}"
        )

    similar_bookmarks = await similarity_service.find_similar_bookmarks(
        new_bookmark_content=content_for_similarity,
        user_id=bookmark_data.user_id,
        keywords=bookmark_data.keywords,
        summary=bookmark_data.summary
    )

    logger.info(
        "📊 유사도 계산 완료 - 유사 북마크 {}개 발견",
        len(similar_bookmarks)
    )
    return similar_bookmarks


async def _publish_relationships(bookmark_data: BookmarkData,
                                 similar_bookmarks: List[Dict]) -> bool:
    """관계 데이터 메시지를 발행합니다."""
    if not similar_bookmarks:
        logger.info("📝 유사한 북마크가 없어 관계 데이터 생성하지 않음")
        return False

    logger.info("📤 관계 데이터 메시지 발행 시작...")
    try:
        success = await message_publisher.publish_bookmark_relationships(
            user_id=bookmark_data.user_id,
            source_bookmark={
                "bookmark_id": bookmark_data.star_id,
                "title": bookmark_data.title,
                "url": bookmark_data.url,
                "keywords": bookmark_data.keywords,
                "summary": bookmark_data.summary
            },
            similar_bookmarks=similar_bookmarks
        )

        if success:
            logger.info(
                "✅ 관계 데이터 메시지 발행 완료 - 유사 북마크 {}개",
                len(similar_bookmarks)
            )
            return True

        logger.warning("⚠️ 관계 데이터 메시지 발행 실패")
        return False

    except (ConnectionError, TimeoutError) as e:
        logger.error("❌ 관계 메시지 발행 중 네트워크 오류: {}", e)
        return False
    except ValueError as e:
        logger.error("❌ 관계 메시지 발행 중 데이터 오류: {}", e)
        return False


async def _delete_existing_data(session, bookmark_data: BookmarkData) -> int:
    """기존 북마크 데이터를 삭제합니다."""
    total_deleted = 0

    # 모든 북마크 관련 데이터를 star_id로 한 번에 삭제
    source_types = ["bookmark_content", "bookmark_memo", "bookmark_summary"]
    
    for source_type in source_types:
        try:
            deleted_count = await vector_service.delete_document(
                session=session,
                user_id=bookmark_data.user_id,
                source_id=bookmark_data.star_id,  # star_id로 통일
                source_type=source_type
            )
            total_deleted += deleted_count
            
            if deleted_count > 0:
                logger.info("🗑️ 기존 데이터 삭제 - source_type: {}, 삭제 수: {}", 
                           source_type, deleted_count)
                           
        except Exception as e:
            logger.warning("기존 데이터 삭제 중 오류 (계속 진행): source_type: {}, 오류: {}", 
                          source_type, e)

    return total_deleted


async def _save_content_chunks(session, bookmark_data: BookmarkData, body_text: str,
                               similar_bookmarks: List[Dict]) -> tuple:
    """콘텐츠 청크들을 저장합니다."""
    # S3 파일이 없어 body_text가 비어있는 경우에도 메타데이터는 저장
    if not body_text:
        logger.info("📝 본문 텍스트가 비어있음 - 메타데이터만으로 벡터 저장 진행")
        # 빈 콘텐츠 대신 메타데이터 정보를 사용
        fallback_content = f"{bookmark_data.title}\n{bookmark_data.summary}\n{bookmark_data.memo}"
        if not fallback_content.strip():
            fallback_content = "북마크 데이터 (본문 없음)"
        
        # 단일 벡터 생성
        chunk_metadata = {
            "chunk_index": 0,
            "total_chunks": 1,
            "user_selected_keywords": bookmark_data.keywords,
            "chunk_keywords": bookmark_data.keywords,
            "user_memo": bookmark_data.memo,
            "user_summary": bookmark_data.summary,
            "s3_key": bookmark_data.s3_key,
            "similar_bookmarks_count": len(similar_bookmarks)
        }

        source_data = {
            "source_id": bookmark_data.star_id,  # 복잡한 패턴 대신 star_id 직접 사용
            "source_type": "bookmark_content",
        }

        chunk_vectors = await vector_service.save_document_chunk(
            session=session,
            user_id=bookmark_data.user_id,
            source_data=source_data,
            content=fallback_content,
            chunk_index=0,  # fallback은 단일 청크
            title=bookmark_data.title,
            url=bookmark_data.url,
            keywords=bookmark_data.keywords,
            summary=bookmark_data.summary,
            extra_metadata=chunk_metadata
        )
        
        logger.info("✅ 메타데이터 벡터 저장 완료 - 청크 수: 1, 벡터 수: {}", len(chunk_vectors))
        return chunk_vectors, 1
    
    # 일반적인 콘텐츠 청크 처리
    logger.info("📝 콘텐츠 청크 생성 및 저장 시작...")
    
    # 청크로 분할 (keywords 매개변수 추가)
    chunks = prepare_content_for_rag(
        text=body_text, 
        keywords=bookmark_data.keywords,
        metadata={
            "memo": bookmark_data.memo,
            "summary": bookmark_data.summary
        }
    )
    
    # 청크에서 content만 추출
    text_chunks = [chunk["content"] for chunk in chunks]
    total_chunks = len(text_chunks)
    all_vectors = []
    
    logger.info("📄 텍스트 분할 완료 - 총 청크 수: {}", total_chunks)
    
    # 각 청크를 개별적으로 처리 (로그는 요약만)
    for i, chunk_text in enumerate(text_chunks):
        chunk_metadata = {
            "chunk_index": i,
            "total_chunks": total_chunks,
            "user_selected_keywords": bookmark_data.keywords,
            "chunk_keywords": bookmark_data.keywords,
            "user_memo": bookmark_data.memo,
            "user_summary": bookmark_data.summary,
            "s3_key": bookmark_data.s3_key,
            "similar_bookmarks_count": len(similar_bookmarks)
        }

        source_data = {
            "source_id": bookmark_data.star_id,  # 복잡한 패턴 대신 star_id 직접 사용
            "source_type": "bookmark_content",
        }

        chunk_vectors = await vector_service.save_document_chunk(
            session=session,
            user_id=bookmark_data.user_id,
            source_data=source_data,
            content=chunk_text,
            chunk_index=i,
            title=bookmark_data.title,
            url=bookmark_data.url,
            keywords=bookmark_data.keywords,
            summary=bookmark_data.summary,
            extra_metadata=chunk_metadata
        )
        
        all_vectors.extend(chunk_vectors)
        
        # 진행 상황 로그 (매 5개 청크마다)
        if (i + 1) % 5 == 0 or i == total_chunks - 1:
            logger.info("🔄 청크 처리 진행 중... ({}/{}) - 누적 벡터: {}", 
                       i + 1, total_chunks, len(all_vectors))

    logger.info("✅ 모든 콘텐츠 청크 저장 완료 - 청크 수: {}, 벡터 수: {}", 
               total_chunks, len(all_vectors))
    
    return all_vectors, total_chunks


async def _save_memo_if_exists(session, bookmark_data: BookmarkData,
                               similar_bookmarks: List[Dict]) -> List:
    """메모가 있으면 저장합니다."""
    if not (bookmark_data.memo and bookmark_data.memo.strip()):
        return []

    memo_metadata = {
        "chunk_type": "user_memo",
        "user_selected_keywords": bookmark_data.keywords,
        "s3_key": bookmark_data.s3_key,
        "original_content_summary": bookmark_data.summary,
        "similar_bookmarks_count": len(similar_bookmarks)
    }

    memo_content = (
        f"사용자 메모: {bookmark_data.memo}\n\n"
        f"관련 키워드: {', '.join(bookmark_data.keywords)}\n\n"
        f"내용 요약: {bookmark_data.summary}"
    )

    source_data = {
        "source_id": bookmark_data.star_id,  # star_id로 통일
        "source_type": "bookmark_memo"
    }

    memo_vectors = await vector_service.save_document_chunk(
        session=session,
        user_id=bookmark_data.user_id,
        source_data=source_data,
        content=memo_content,
        chunk_index=0,  # 메모는 단일 청크
        title=f"[메모] {bookmark_data.title}",
        url=bookmark_data.url,
        keywords=bookmark_data.keywords,
        summary=bookmark_data.memo,
        extra_metadata=memo_metadata
    )
    return memo_vectors


async def _save_summary_if_exists(session, bookmark_data: BookmarkData,
                                  similar_bookmarks: List[Dict], rag_chunks: List) -> List:
    """요약이 있으면 저장합니다."""
    if not (bookmark_data.summary and bookmark_data.summary.strip()):
        return []

    summary_metadata = {
        "chunk_type": "summary",
        "user_selected_keywords": bookmark_data.keywords,
        "s3_key": bookmark_data.s3_key,
        "total_content_chunks": len(rag_chunks),
        "similar_bookmarks_count": len(similar_bookmarks)
    }

    summary_content = (
        f"문서 요약: {bookmark_data.summary}\n\n"
        f"핵심 키워드: {', '.join(bookmark_data.keywords)}"
    )

    source_data = {
        "source_id": bookmark_data.star_id,  # star_id로 통일
        "source_type": "bookmark_summary"
    }

    summary_vectors = await vector_service.save_document_chunk(
        session=session,
        user_id=bookmark_data.user_id,
        source_data=source_data,
        content=summary_content,
        chunk_index=0,  # 요약은 단일 청크
        title=f"[요약] {bookmark_data.title}",
        url=bookmark_data.url,
        keywords=bookmark_data.keywords,
        summary=bookmark_data.summary,
        extra_metadata=summary_metadata
    )
    return summary_vectors


async def _trigger_profile_update_event(bookmark_data: BookmarkData) -> Dict:
    """
    북마크 저장 완료 후 사용자 프로필 업데이트를 직접 처리합니다.
    
    Args:
        bookmark_data: 북마크 데이터
        
    Returns:
        프로필 업데이트 결과
    """
    try:
        logger.info("🔄 사용자 프로필 업데이트 처리 시작 - user_id: {}, star_id: {}", 
                   bookmark_data.user_id, bookmark_data.star_id)
        
        # 세션을 직접 가져와서 처리
        async for session in get_async_session():
            try:
                # Repository 인스턴스 생성
                repos = create_repositories()
                
                # 1. 기존 프로필 조회 또는 생성
                profile = await repos['user_profile_repo'].get_or_create_profile(
                    session, bookmark_data.user_id
                )
                
                # 2. 간단한 활동 데이터 생성 (메모리 최적화)
                content = f"{bookmark_data.title}. {bookmark_data.summary}"[:500]  # 길이 제한
                
                activity_data = ActivityData(
                    activity_type=ActivityType.BOOKMARK,
                    content=content,
                    created_at=datetime.now(),
                    metadata={
                        "url": bookmark_data.url,
                        "category": "bookmark",
                        "source": "bookmark_save_task"
                    },
                    weight=1.5
                )
                
                # 3. 메모리 효율적인 벡터 업데이트
                openai_service = OpenAIService()
                vector_generator = VectorGenerator(openai_service)
                
                if profile.profile_vector is not None and len(profile.profile_vector) > 0:
                    logger.info("🔄 기존 벡터 증분 업데이트 - user_id: {}", bookmark_data.user_id)
                    updated_vector, update_metadata = await vector_generator.update_vector_incrementally(
                        profile.profile_vector, [activity_data]
                    )
                else:
                    logger.info("🆕 새 벡터 생성 - user_id: {}", bookmark_data.user_id)
                    updated_vector, update_metadata = await vector_generator.generate_profile_vector(
                        [activity_data]
                    )
                
                # 4. 프로필 저장 (필수 필드만)
                await repos['user_profile_repo'].update_profile(
                    session,
                    bookmark_data.user_id,
                    profile_vector=updated_vector,
                    vector_strength=update_metadata.get('vector_strength', 0.0),
                    last_activity_at=datetime.now()
                )
                
                await session.commit()
                
                # 5. 프로파일 업데이트 리스너에 이벤트 트리거 (if available)
                try:
                    from app.main import get_profile_listener
                    profile_listener = get_profile_listener()
                    
                    if profile_listener:
                        # 북마크 추가 이벤트 트리거
                        await profile_listener.handle_bookmark_event(
                            user_id=bookmark_data.user_id,
                            event_type="added",
                            bookmark_data={
                                "star_id": bookmark_data.star_id,
                                "title": bookmark_data.title,
                                "url": bookmark_data.url,
                                "keywords": bookmark_data.keywords,
                                "summary": bookmark_data.summary
                            },
                            metadata={
                                "profile_update_method": "optimized_update",
                                "processing_timestamp": datetime.now().isoformat()
                            }
                        )
                        logger.info("🎯 프로파일 업데이트 이벤트 트리거 완료 - user_id: {}", bookmark_data.user_id)
                    else:
                        logger.warning("⚠️ 프로파일 업데이트 리스너가 실행 중이지 않음 - user_id: {}", bookmark_data.user_id)
                        
                except Exception as event_error:
                    logger.warning("⚠️ 프로파일 업데이트 이벤트 트리거 실패 (계속 진행): {}", event_error)
                
                # 6. 메모리 정리
                del activity_data, updated_vector, update_metadata, openai_service, vector_generator
                
                logger.info("✅ 사용자 프로필 업데이트 완료 - user_id: {}", bookmark_data.user_id)
                
                return {
                    "success": True,
                    "method": "optimized_update",
                    "user_id": bookmark_data.user_id,
                    "timestamp": datetime.now()
                }
                
            except Exception as session_error:
                await session.rollback()
                raise session_error
                
    except Exception as e:
        logger.error("❌ 사용자 프로필 업데이트 실패 - user_id: {}, 오류: {}", 
                    bookmark_data.user_id, e)
        
        return {
            "success": False,
            "method": "optimized_update",
            "error": str(e),
            "user_id": bookmark_data.user_id,
            "error_type": type(e).__name__,
            "timestamp": datetime.now()
        }


def _save_bookmark_logic(bookmark_data: BookmarkData) -> dict:
    """
    북마크의 완전한 처리 워크플로우를 수행하는 핵심 로직 함수

    이 함수는 전체 북마크 처리 과정을 담당합니다:
    1. S3에서 HTML 콘텐츠 다운로드
    2. 유사도 계산 (기존 북마크와 비교)
    3. 관계 메시지 발행 (Spring Boot로 전송)
    4. PostgreSQL 벡터 데이터베이스에 저장

    Args:
        bookmark_data (BookmarkData): 북마크 데이터

    Returns:
        dict: 처리 결과 및 상세 정보
    """
    async def _async_save_logic():
        """비동기 로직 실행"""
        session = None
        try:
            # get_async_session을 컨텍스트 매니저로 사용
            async_session_gen = get_async_session()
            session = await async_session_gen.__anext__()
            
            total_deleted = 0  # 변수 초기화
            logger.info("📊 벡터 데이터베이스 저장 시작 - user_id: {}, star_id: {}", 
                       bookmark_data.user_id, bookmark_data.star_id)
            
            # 벡터 서비스 로그 레벨을 일시적으로 조정 (WARNING으로 변경)
            vector_logger = logging.getLogger("app.services.vector_service")
            repo_logger = logging.getLogger("app.repositories.vector_repository")
            original_vector_level = vector_logger.level
            original_repo_level = repo_logger.level
            
            try:
                # 로그 레벨을 WARNING으로 설정하여 INFO 로그 숨기기
                vector_logger.setLevel(logging.WARNING)
                repo_logger.setLevel(logging.WARNING)
                
                # 4-0. 기존 북마크 데이터 삭제 (업데이트 처리)
                total_deleted = await _delete_existing_data(session, bookmark_data)
                if total_deleted > 0:
                    logger.info("🗑️ 기존 북마크 데이터 삭제 완료 - 벡터 수: {}", total_deleted)
                
                # 4-1. S3 파일 다운로드 및 텍스트 추출
                body_text = await _download_and_extract_content(bookmark_data.s3_key, bookmark_data.url)

                # 4-2. 유사도 계산
                similar_bookmarks = await _calculate_similarity(bookmark_data, body_text)

                # 4-3. 관계 메시지 발행 (Spring Boot로 전송)
                await _publish_relationships(bookmark_data, similar_bookmarks)

                # 4-4. 콘텐츠 청크 저장
                saved_vectors, total_chunks = await _save_content_chunks(
                    session, bookmark_data, body_text, similar_bookmarks
                )

                # 4-5. 메모 저장 (있는 경우)
                memo_vectors = await _save_memo_if_exists(
                    session, bookmark_data, similar_bookmarks
                )
                saved_vectors.extend(memo_vectors)

                # 4-6. 요약 저장 (있는 경우)
                summary_vectors = await _save_summary_if_exists(
                    session, bookmark_data, similar_bookmarks, saved_vectors
                )
                saved_vectors.extend(summary_vectors)
                
                # 트랜잭션 커밋
                await session.commit()
                
            finally:
                # 로그 레벨 원복
                vector_logger.setLevel(original_vector_level)
                repo_logger.setLevel(original_repo_level)

            logger.info("✅ 벡터 데이터베이스 저장 완료 - 벡터 수: {}", len(saved_vectors))
            
            # 프로필 업데이트 이벤트 트리거
            result = await _trigger_profile_update_event(bookmark_data)
            
            return {
                "status": "success",
                "inserted": len(saved_vectors),
                "deleted": total_deleted,
                "content_chunks": total_chunks,
                "has_memo": bool(bookmark_data.memo and bookmark_data.memo.strip()),
                "has_summary": bool(bookmark_data.summary and bookmark_data.summary.strip()),
                "total_keywords": len(bookmark_data.keywords),
                "user_keywords": len(bookmark_data.keywords),
                "user_title": bookmark_data.title,
                "user_url": bookmark_data.url,
                "is_update": total_deleted > 0,
                "similar_bookmarks_found": len(similar_bookmarks),
                "relationship_published": True,
                "content_length": len(body_text),
                "profile_update_result": result
            }

        except Exception as e:
            logger.error("❌ 비동기 로직 실행 중 오류: {}", e)
            if session:
                try:
                    await session.rollback()
                except Exception as rollback_error:
                    logger.error("❌ 롤백 중 오류: {}", rollback_error)
            raise
        finally:
            # 세션 안전하게 종료
            if session:
                try:
                    await session.close()
                except Exception as close_error:
                    logger.error("❌ 세션 종료 중 오류: {}", close_error)

    # Celery 워커 환경에서 안전한 비동기 실행
    return run_async_safely(_async_save_logic(), timeout=300)


@celery.task(
    name="tasks.save_bookmark",
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
    retry_jitter=True,
)
def save_bookmark_task(_self, bookmark_data_dict: dict) -> dict:
    """
    북마크의 완전한 처리 워크플로우를 수행하는 Celery 태스크

    이 태스크는 북마크 저장의 모든 단계를 처리합니다:
    1. S3 HTML 다운로드 및 텍스트 추출
    2. 유사도 계산 (기존 북마크와 비교)
    3. 관계 메시지 발행 (Spring Boot로 전송)
    4. PostgreSQL 벡터 데이터베이스 저장

    예외 발생 시 최대 3회까지 자동으로 재시도하며,
    재시도 간격은 지수적으로 증가하고 무작위 지터가 추가됩니다.

    Args:
        _self: Celery 태스크 인스턴스 (bind=True로 인해 자동 주입)
        bookmark_data_dict (dict): 북마크 데이터 딕셔너리

    Returns:
        dict: 처리 결과 및 상세 정보
    """
    start_time = time.time()
    user_id = bookmark_data_dict.get("user_id", "unknown")
    star_id = bookmark_data_dict.get("star_id", "unknown")
    
    logger.info(
        "🚀 북마크 완전 처리 태스크 시작 - user_id: {}, star_id: {}",
        user_id, star_id
    )

    try:
        # 북마크 작업 메트릭 증가
        prometheus_metrics.increment_bookmark_operation("save", "started")
        
        bookmark_data = BookmarkData(**bookmark_data_dict)
        result = _save_bookmark_logic(bookmark_data)

        # result가 None인 경우 처리
        if result is None:
            logger.error("❌ 북마크 처리 로직에서 None 반환 - star_id: {}", bookmark_data.star_id)
            result = {
                "status": "error",
                "error": "처리 결과가 None입니다."
            }
            # 실패 메트릭 기록
            duration = time.time() - start_time
            prometheus_metrics.record_celery_task("save_bookmark", "error", duration)
            prometheus_metrics.increment_bookmark_operation("save", "error")
        else:
            # 성공 메트릭 기록
            duration = time.time() - start_time
            prometheus_metrics.record_celery_task("save_bookmark", "success", duration)
            prometheus_metrics.increment_bookmark_operation("save", "success")

        logger.info(
            "✅ 북마크 완전 처리 태스크 완료 - star_id: {}, 결과: {}",
            bookmark_data.star_id,
            result.get("status", "unknown")
        )
        return result

    except (ConnectionError, TimeoutError) as e:
        # 네트워크 오류 메트릭 기록
        duration = time.time() - start_time
        prometheus_metrics.record_celery_task("save_bookmark", "network_error", duration)
        prometheus_metrics.increment_bookmark_operation("save", "network_error")
        
        error_msg = f"북마크 처리 태스크 네트워크 오류 - user_id: {user_id}, star_id: {star_id}, 오류: {e}"
        logger.error(f"❌ {error_msg}")
        
        # 서버 로그에도 기록 (print를 사용하여 stdout으로 출력)
        print(f"[CELERY ERROR] {error_msg}")
        
        # 재시도 정보 로깅
        if hasattr(_self, 'retry_state') and _self.retry_state:
            retry_count = _self.retry_state.attempt_number
            logger.error(f"🔄 재시도 {retry_count}/3 - star_id: {star_id}")
            print(f"[CELERY RETRY] 재시도 {retry_count}/3 - star_id: {star_id}")
        
        raise
        
    except ValueError as e:
        # 데이터 오류 메트릭 기록
        duration = time.time() - start_time
        prometheus_metrics.record_celery_task("save_bookmark", "data_error", duration)
        prometheus_metrics.increment_bookmark_operation("save", "data_error")
        
        error_msg = f"북마크 처리 태스크 데이터 오류 - user_id: {user_id}, star_id: {star_id}, 오류: {e}"
        logger.error(f"❌ {error_msg}")
        
        # 서버 로그에도 기록
        print(f"[CELERY ERROR] {error_msg}")
        
        # 데이터 오류는 재시도하지 않음
        raise
        
    except Exception as e:
        # 일반 오류 메트릭 기록
        duration = time.time() - start_time
        prometheus_metrics.record_celery_task("save_bookmark", "error", duration)
        prometheus_metrics.increment_bookmark_operation("save", "error")
        
        error_msg = f"북마크 처리 태스크 실패 - user_id: {user_id}, star_id: {star_id}, 오류: {e}"
        logger.error(f"❌ {error_msg}")
        
        # 서버 로그에도 기록
        print(f"[CELERY ERROR] {error_msg}")
        
        # 재시도 정보 로깅
        if hasattr(_self, 'retry_state') and _self.retry_state:
            retry_count = _self.retry_state.attempt_number
            logger.error(f"🔄 재시도 {retry_count}/3 - star_id: {star_id}")
            print(f"[CELERY RETRY] 재시도 {retry_count}/3 - star_id: {star_id}")
        
        raise
