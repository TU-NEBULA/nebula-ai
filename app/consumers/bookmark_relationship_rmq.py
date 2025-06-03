"""
북마크 관계 저장 메시지 소비자 모듈 (Spring Boot용 참고 코드)

이 모듈은 Spring Boot 서버에서 구현해야 할 Consumer의 참고 코드입니다.
AI 서버에서 전송한 북마크 관계 데이터를 수신하여 Neo4j에 저장합니다.

실제로는 Spring Boot에서 구현되어야 하며, 여기서는 참고용으로만 제공합니다.
"""
import logging
from typing import List, Dict

from aio_pika import IncomingMessage
from pydantic import ValidationError

from app.core.rabbit import get_rabbit_connection
from app.core.config import settings
from app.models.bookmark import BookmarkRelationshipMessage
from app.external.springboot_service import SpringBootService, BookmarkNode

log = logging.getLogger(__name__)

# 이 Consumer는 실제로는 Spring Boot에서 구현되어야 합니다!
# 여기서는 참고용 코드만 제공합니다.

async def on_bookmark_relationship_save(message: IncomingMessage):
    """
    북마크 관계 저장 메시지 처리 핸들러 (Spring Boot에서 구현 필요)
    
    Args:
        message (IncomingMessage): RabbitMQ에서 받은 메시지 객체
    """
    async with message.process():
        try:
            req = BookmarkRelationshipMessage.model_validate_json(message.body)
            log.info(
                "BookmarkRelationship 요청 수신, user_id=%s, bookmark_id=%s, 관계수=%d", 
                req.user_id,
                req.source_bookmark.get("bookmark_id"),
                len(req.similar_bookmarks)
            )
            
            # Spring Boot에서 구현할 내용:
            # 1. 새 북마크 노드를 Neo4j에 생성
            # 2. 유사한 북마크들과의 관계를 Neo4j에 생성
            # 3. 양방향 관계 설정 (선택사항)
            
            # 예시 (실제로는 Spring Boot에서 Neo4j Repository 사용):
            # await create_bookmark_node_in_neo4j(req.source_bookmark)
            # await create_relationships_in_neo4j(req.source_bookmark, req.similar_bookmarks)
            
            log.info("북마크 관계 저장 완료 - bookmark_id=%s", req.source_bookmark.get("bookmark_id"))

        except ValidationError as e:
            log.error("Invalid relationship payload: %s", e)
            return
        except Exception as e:
            log.error("북마크 관계 저장 처리 중 오류: %s", e)
            return

async def start_bookmark_relationship_consumer():
    """
    북마크 관계 저장 콘슈머 시작 (Spring Boot에서 구현 필요)
    
    실제로는 Spring Boot에서 RabbitMQ Consumer를 구현해야 합니다.
    """
    conn = await get_rabbit_connection()
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=1)

    queue = await channel.declare_queue(
        settings.BOOKMARK_RELATIONSHIP_QUEUE, durable=True
    )
    await queue.consume(on_bookmark_relationship_save)
    log.info("BookmarkRelationship Consumer listening on %s", queue.name)

# =====================================
# Spring Boot에서 구현해야 할 내용 예시:
# =====================================

"""
Spring Boot Controller 예시:

@RestController
@RequestMapping("/api/bookmarks")
public class BookmarkController {
    
    @Autowired
    private BookmarkService bookmarkService;
    
    @RabbitListener(queues = "bookmark_relationship")
    public void handleBookmarkRelationship(
        @Payload BookmarkRelationshipMessage message
    ) {
        try {
            // 1. 북마크 노드 생성
            bookmarkService.createBookmarkNode(message.getSourceBookmark());
            
            // 2. 관계 생성
            bookmarkService.createRelationships(
                message.getSourceBookmark(),
                message.getSimilarBookmarks()
            );
            
            log.info("북마크 관계 저장 완료: {}", 
                message.getSourceBookmark().getBookmarkId());
                
        } catch (Exception e) {
            log.error("북마크 관계 저장 실패", e);
        }
    }
}

@Service
public class BookmarkService {
    
    @Autowired
    private BookmarkRepository bookmarkRepository;
    
    public void createBookmarkNode(Map<String, Object> bookmarkData) {
        // Neo4j에 북마크 노드 생성
        BookmarkNode node = new BookmarkNode();
        node.setBookmarkId((String) bookmarkData.get("bookmark_id"));
        node.setTitle((String) bookmarkData.get("title"));
        node.setUrl((String) bookmarkData.get("url"));
        node.setKeywords((List<String>) bookmarkData.get("keywords"));
        node.setSummary((String) bookmarkData.get("summary"));
        
        bookmarkRepository.save(node);
    }
    
    public void createRelationships(
        Map<String, Object> sourceBookmark,
        List<Map<String, Object>> similarBookmarks
    ) {
        String sourceId = (String) sourceBookmark.get("bookmark_id");
        
        for (Map<String, Object> similar : similarBookmarks) {
            String targetId = (String) similar.get("bookmark_id");
            Double similarity = (Double) similar.get("similarity_score");
            
            // 관계 생성
            bookmarkRepository.createSimilarityRelationship(
                sourceId, targetId, similarity
            );
        }
    }
}
""" 