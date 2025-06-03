"""
북마크 저장 태스크 모듈

이 모듈은 웹 페이지 북마크의 완전한 처리 워크플로우를 담당하는 Celery 태스크를 정의합니다:
1. S3에서 HTML 콘텐츠 다운로드
2. 유사도 계산 및 관계 데이터 생성
3. 관계 메시지 발행 (Spring Boot로 전송)
4. PostgreSQL 벡터 데이터베이스에 저장

모든 무거운 작업을 백그라운드에서 처리하여 Consumer의 성능을 최적화합니다.
"""

from dataclasses import dataclass
from typing import List, Dict
import asyncio

from loguru import logger
from app.core.celery_worker import celery
from app.core.database import get_async_session
from app.external.s3_service import download_html_from_s3
from app.services.vector_service import vector_service
from app.services.similarity_service import SimilarityService
from app.services.message_publisher import message_publisher
from app.utils.text_processing import extract_main_text, prepare_content_for_rag

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


async def _download_and_extract_content(s3_key: str) -> str:
    """S3에서 HTML을 다운로드하고 텍스트를 추출합니다."""
    logger.info("📥 S3에서 HTML 다운로드 시작 - s3_key: {}", s3_key)
    html = download_html_from_s3(s3_key)

    body_text = extract_main_text(html)
    logger.info("📄 텍스트 추출 완료 - 길이: {}", len(body_text))
    return body_text


async def _calculate_similarity(bookmark_data: BookmarkData, body_text: str) -> List[Dict]:
    """유사도 계산을 수행합니다."""
    logger.info("🔍 유사도 계산 시작...")
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

    # 기존 콘텐츠 청크들 삭제
    for source_type in ["bookmark", "bookmark_chunk"]:
        deleted_count = await vector_service.delete_document(
            session=session,
            user_id=bookmark_data.user_id,
            source_id=bookmark_data.star_id,
            source_type=source_type
        )
        total_deleted += deleted_count

    # 특별한 형태의 source_id들도 삭제
    try:
        patterns = [
            f"{bookmark_data.star_id}_chunk_",
            f"{bookmark_data.star_id}_memo",
            f"{bookmark_data.star_id}_summary"
        ]

        for pattern in patterns:
            try:
                pattern_deleted = await vector_service.delete_documents_by_pattern(
                    session=session,
                    user_id=bookmark_data.user_id,
                    source_id_pattern=pattern
                )
                total_deleted += pattern_deleted
            except AttributeError:
                # delete_documents_by_pattern이 없는 경우 개별 삭제
                deleted_count = await _delete_pattern_individually(
                    session, bookmark_data, pattern
                )
                total_deleted += deleted_count

    except (ConnectionError, TimeoutError) as e:
        logger.warning("기존 데이터 삭제 중 네트워크 오류 (계속 진행): {}", e)
    except ValueError as e:
        logger.warning("기존 데이터 삭제 중 데이터 오류 (계속 진행): {}", e)

    return total_deleted


async def _delete_pattern_individually(session, bookmark_data: BookmarkData, pattern: str) -> int:
    """패턴별로 개별 삭제를 수행합니다."""
    total_deleted = 0

    if "_chunk_" in pattern:
        for i in range(20):
            chunk_deleted = await vector_service.delete_document(
                session=session,
                user_id=bookmark_data.user_id,
                source_id=f"{bookmark_data.star_id}_chunk_{i}",
                source_type="bookmark_chunk"
            )
            total_deleted += chunk_deleted
            if chunk_deleted == 0:
                break
    elif "_memo" in pattern:
        deleted_count = await vector_service.delete_document(
            session=session,
            user_id=bookmark_data.user_id,
            source_id=f"{bookmark_data.star_id}_memo",
            source_type="bookmark_memo"
        )
        total_deleted += deleted_count
    elif "_summary" in pattern:
        deleted_count = await vector_service.delete_document(
            session=session,
            user_id=bookmark_data.user_id,
            source_id=f"{bookmark_data.star_id}_summary",
            source_type="bookmark_summary"
        )
        total_deleted += deleted_count

    return total_deleted


async def _save_content_chunks(session, bookmark_data: BookmarkData, body_text: str,
                               similar_bookmarks: List[Dict]) -> tuple:
    """콘텐츠 청크들을 저장합니다."""
    rag_chunks = prepare_content_for_rag(
        text=body_text,
        keywords=bookmark_data.keywords,
        memo=bookmark_data.memo,
        summary=bookmark_data.summary,
        chunk_size=1000,
        chunk_overlap=200
    )

    saved_vectors = []
    for chunk_data in rag_chunks:
        chunk_metadata = {
            "chunk_index": chunk_data["chunk_index"],
            "total_chunks": chunk_data["total_chunks"],
            "user_selected_keywords": bookmark_data.keywords,
            "chunk_keywords": chunk_data["chunk_keywords"],
            "user_memo": bookmark_data.memo,
            "s3_key": bookmark_data.s3_key,
            "chunk_type": "content",
            "similar_bookmarks_count": len(similar_bookmarks)
        }

        chunk_vectors = await vector_service.save_document(
            session=session,
            user_id=bookmark_data.user_id,
            source_id=f"{bookmark_data.star_id}_chunk_{chunk_data['chunk_index']}",
            source_type="bookmark_chunk",
            content=chunk_data["content"],
            title=bookmark_data.title,
            url=bookmark_data.url,
            keywords=bookmark_data.keywords,
            summary=bookmark_data.summary,
            extra_metadata=chunk_metadata
        )
        saved_vectors.extend(chunk_vectors)

    return saved_vectors, rag_chunks


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

    memo_vectors = await vector_service.save_document(
        session=session,
        user_id=bookmark_data.user_id,
        source_id=f"{bookmark_data.star_id}_memo",
        source_type="bookmark_memo",
        content=memo_content,
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

    summary_vectors = await vector_service.save_document(
        session=session,
        user_id=bookmark_data.user_id,
        source_id=f"{bookmark_data.star_id}_summary",
        source_type="bookmark_summary",
        content=summary_content,
        title=f"[요약] {bookmark_data.title}",
        url=bookmark_data.url,
        keywords=bookmark_data.keywords,
        summary=bookmark_data.summary,
        extra_metadata=summary_metadata
    )
    return summary_vectors


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
        # 1. S3에서 HTML 다운로드 및 텍스트 추출
        body_text = await _download_and_extract_content(bookmark_data.s3_key)

        # 2. 유사도 계산 수행
        similar_bookmarks = await _calculate_similarity(bookmark_data, body_text)

        # 3. 관계 데이터 메시지 발행
        relationship_published = await _publish_relationships(bookmark_data, similar_bookmarks)

        # 4. PostgreSQL 벡터 데이터베이스 저장
        logger.info("💾 벡터 데이터베이스 저장 시작...")

        async for session in get_async_session():
            # 4-1. 기존 데이터 삭제
            total_deleted = await _delete_existing_data(session, bookmark_data)

            # 4-2. 콘텐츠 청크 저장
            saved_vectors, rag_chunks = await _save_content_chunks(
                session, bookmark_data, body_text, similar_bookmarks
            )

            # 4-3. 메모 저장 (있는 경우)
            memo_vectors = await _save_memo_if_exists(session, bookmark_data, similar_bookmarks)
            saved_vectors.extend(memo_vectors)

            # 4-4. 요약 저장 (있는 경우)
            summary_vectors = await _save_summary_if_exists(
                session, bookmark_data, similar_bookmarks, rag_chunks
            )
            saved_vectors.extend(summary_vectors)

            logger.info("✅ 벡터 데이터베이스 저장 완료 - 벡터 수: {}", len(saved_vectors))

            return {
                "status": "success",
                "inserted": len(saved_vectors),
                "deleted": total_deleted,
                "content_chunks": len(rag_chunks),
                "has_memo": bool(bookmark_data.memo and bookmark_data.memo.strip()),
                "has_summary": bool(bookmark_data.summary and bookmark_data.summary.strip()),
                "total_keywords": len(bookmark_data.keywords),
                "user_keywords": len(bookmark_data.keywords),
                "user_title": bookmark_data.title,
                "user_url": bookmark_data.url,
                "is_update": total_deleted > 0,
                "similar_bookmarks_found": len(similar_bookmarks),
                "relationship_published": relationship_published,
                "content_length": len(body_text)
            }

    # 비동기 함수를 동기로 실행
    return asyncio.run(_async_save_logic())


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
    logger.info(
        "🚀 북마크 완전 처리 태스크 시작 - user_id: {}, star_id: {}",
        bookmark_data_dict.get("user_id"),
        bookmark_data_dict.get("star_id")
    )

    try:
        bookmark_data = BookmarkData(**bookmark_data_dict)
        result = _save_bookmark_logic(bookmark_data)

        logger.info(
            "✅ 북마크 완전 처리 태스크 완료 - star_id: {}, 결과: {}",
            bookmark_data.star_id,
            result["status"]
        )
        return result

    except (ConnectionError, TimeoutError) as e:
        logger.error(
            "❌ 북마크 처리 태스크 네트워크 오류 - star_id: {}, 오류: {}",
            bookmark_data_dict.get("star_id"),
            e
        )
        raise
    except ValueError as e:
        logger.error(
            "❌ 북마크 처리 태스크 데이터 오류 - star_id: {}, 오류: {}",
            bookmark_data_dict.get("star_id"),
            e
        )
        raise
    except Exception as e:
        logger.error(
            "❌ 북마크 처리 태스크 실패 - star_id: {}, 오류: {}",
            bookmark_data_dict.get("star_id"),
            e
        )
        raise
