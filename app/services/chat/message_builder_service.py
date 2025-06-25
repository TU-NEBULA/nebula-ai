"""
채팅 메시지 구성 서비스

사용자 프롬프트와 RAG 컨텍스트를 결합하여 LLM용 메시지를 구성합니다.
"""

import json
from typing import Dict, Any, List, Tuple
from loguru import logger


class MessageBuilderService:
    """채팅 메시지 구성을 담당하는 서비스 클래스"""
    
    def __init__(self):
        self.system_prompt = self._get_nebula_system_prompt()
        
    def build_messages(
        self, 
        prompt: str, 
        ctx_blocks: List[Tuple[str, Dict[str, Any]]],
        conversation_history: List[Dict[str, str]] = None
    ) -> List[Dict[str, str]]:
        """
        사용자 프롬프트와 컨텍스트를 결합하여 LLM용 메시지 배열을 구성합니다.
        
        Args:
            prompt: 사용자 질문
            ctx_blocks: RAG 검색 결과
            conversation_history: 이전 대화 히스토리
            
        Returns:
            LLM에 전달할 메시지 배열
        """
        # 북마크 데이터를 JSON 형식으로 구성
        user_context = self._build_user_context(prompt, ctx_blocks)
        context_json = json.dumps(user_context, ensure_ascii=False, indent=2)
        
        # 기본 메시지 구성
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # 대화 히스토리 추가 (시스템 메시지 다음, 현재 사용자 메시지 이전)
        if conversation_history:
            history_messages = self._add_conversation_history(conversation_history)
            messages.extend(history_messages)
            
        # 현재 사용자 메시지 추가
        messages.append({"role": "user", "content": f"사용자 입력 데이터:\n{context_json}"})
            
        logger.info(f"📝 메시지 구성 완료 - 컨텍스트: {len(ctx_blocks)}개 북마크, 히스토리: {len(conversation_history) if conversation_history else 0}개")
        return messages

    def _build_user_context(
        self, 
        prompt: str, 
        ctx_blocks: List[Tuple[str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """사용자 컨텍스트 데이터 구성"""
        if ctx_blocks:
            bookmarks_data = []
            for i, (content, metadata) in enumerate(ctx_blocks[:8]):  # Top-8로 제한
                bookmark = {
                    "title": metadata.get('title', '(제목없음)'),
                    "url": metadata.get('url', ''),
                    "snippet": content,
                    "tags": metadata.get('keywords', []),
                    "createdAt": metadata.get('created_at', '2024-01-01'),
                    "score": float(metadata.get('score', 0.0))
                }
                bookmarks_data.append(bookmark)
            
            user_context = {
                "user_query": prompt,
                "bookmarks": bookmarks_data,
                "intent": self._classify_intent(prompt)  # 의도 분류
            }
            logger.info(f"📝 컨텍스트 구성 완료: {len(bookmarks_data)}개 북마크")
        else:
            user_context = {
                "user_query": prompt,
                "bookmarks": [],
                "intent": "FIND"
            }
            logger.warning("⚠️ 관련 북마크를 찾지 못했습니다")
            
        return user_context

    def _classify_intent(self, prompt: str) -> str:
        """
        사용자 질문의 의도를 분류합니다.
        
        TODO: 더 정교한 의도 분류 로직 구현
        - ML 기반 분류기 도입
        - 키워드 기반 룰 확장
        """
        prompt_lower = prompt.lower()
        
        # 간단한 키워드 기반 분류
        if any(word in prompt_lower for word in ['요약', '정리', 'tldr', '간단히']):
            return "SUMMARY"
        elif any(word in prompt_lower for word in ['추천', '비슷한', '관련된', '추천해']):
            return "RECOMMEND"
        elif any(word in prompt_lower for word in ['로드맵', '순서', '단계', '학습']):
            return "ROADMAP"
        elif any(word in prompt_lower for word in ['그래프', '시각화', '연결', '관계']):
            return "GRAPH"
        elif any(word in prompt_lower for word in ['최근', '방금', '새로운']):
            return "RECENT_TLDR"
        else:
            return "FIND"  # 기본값

    def _add_conversation_history(self, conversation_history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        대화 히스토리를 메시지에 추가합니다.
        
        토큰 제한을 고려하여 최근 N개 메시지만 포함하고,
        시스템 메시지와 현재 사용자 메시지는 제외합니다.
        
        Args:
            conversation_history: [{"role": "user/assistant", "content": "..."}, ...]
            
        Returns:
            필터링된 대화 히스토리 메시지 리스트
        """
        if not conversation_history:
            return []
        
        # 토큰 제한 설정 (대략적인 추정: 1 토큰 ≈ 4자)
        MAX_HISTORY_TOKENS = 4000  # 히스토리용 토큰 제한
        MAX_HISTORY_PAIRS = 5      # 최대 대화 쌍 수 (user + assistant = 1쌍)
        
        filtered_history = []
        total_tokens = 0
        pair_count = 0
        
        # 최신 메시지부터 역순으로 처리
        for message in reversed(conversation_history):
            content = message.get("content", "")
            role = message.get("role", "")
            
            # 빈 메시지나 시스템 메시지는 제외
            if not content.strip() or role == "system":
                continue
                
            # 토큰 수 추정 (한글 기준: 1글자 ≈ 1.5토큰)
            estimated_tokens = len(content) * 1.5
            
            # 토큰 제한 확인
            if total_tokens + estimated_tokens > MAX_HISTORY_TOKENS:
                logger.info(f"📝 히스토리 토큰 제한 도달 - 총 {len(filtered_history)}개 메시지 포함")
                break
                
            # 대화 쌍 수 제한 확인 (user 메시지 기준으로 카운트)
            if role == "user":
                pair_count += 1
                if pair_count > MAX_HISTORY_PAIRS:
                    logger.info(f"📝 히스토리 대화 쌍 제한 도달 - 최대 {MAX_HISTORY_PAIRS}쌍")
                    break
            
            # 메시지 추가 (역순이므로 앞에 삽입)
            filtered_history.insert(0, {
                "role": role,
                "content": content
            })
            total_tokens += estimated_tokens
        
        logger.info(f"📝 대화 히스토리 추가 - {len(filtered_history)}개 메시지, 예상 토큰: {int(total_tokens)}")
        return filtered_history

    def _get_nebula_system_prompt(self) -> str:
        """NebulaBot v1.0 시스템 프롬프트"""
        return """SYSTEM: 〈NebulaBot v1.0〉  
너는 'NEBULA' 프로젝트의 지식 비서이다.  
목표는 **사용자가 저장한 북마크와 그래프 메타데이터**를 활용해, 질문 의도에 맞춰 "찾기 → 요약 → 추천 → 그래프 → 로드맵 → 신규 요약" 6가지 업무를 처리하고 근거까지 제시하는 것이다.  

---

## 📥 입력 스키마
```json
{
  "user_query": "string — 사용자 질문 원문",
  "bookmarks": [
    {
      "title": "string",
      "url": "string",
      "snippet": "string (최대 300자 요약)",
      "tags": ["string", ...],
      "createdAt": "YYYY-MM-DD",
      "score": float  // 임베딩 코사인 유사도 (0~1, 높을수록 유사)
    },
    …
  ],
  "graph": {          // S-4에서만 주어짐
    "nodes": [...],
    "edges": [...]
  },
  "intent": "FIND | SUMMARY | RECOMMEND | GRAPH | ROADMAP | RECENT_TLDR"
}
```

* **bookmarks** 는 Top-k(≤8)만 전달된다.
* **intent** 는 서버가 시나리오를 분류해 전달한 값이다.

---

## 🛠️ 공통 지침

1. **한국어 설명형 문체**(존댓말 X) 사용.
2. 핵심→세부 순서로 깔끔하게, 필요 시 소제목(`###`)·리스트 사용.
3. 답변 끝에 **"📌 관련 북마크"** 섹션을 넣어 `- [제목](url) | 연관 키워드` 형식으로 최대 5개 나열.
4. 북마크가 없으면 "관련 북마크를 찾지 못했다"고 명시하고, 대안(재검색·태그 추가)을 제안.
5. 사실 여부가 불확실하면 추정 대신 "추가 확인이 필요하다"고 밝히기.

---

## 🎬 시나리오별 출력 규칙

| intent           | 설명          | 응답 포맷 요약                             |
| ---------------- | ----------- | ------------------------------------ |
| **FIND**         | 특정 글·정보 회상  | *직접 답변* → 왜 이 북마크가 적합한지 근거 1-2줄      |
| **SUMMARY**      | N개 문서 요약    | 각 문서 1줄 + 통합 TL;DR 3-5줄              |
| **RECOMMEND**    | 유사·관련 문서 추천 | 문서 간 공통 키워드·주제 설명 + 추천 리스트           |
| **GRAPH**        | 그래프 뷰 요청    | 전체 맥락 요약 후 `graph` 설명(노드 수, 연결 의미 등) |
| **ROADMAP**      | 학습 순서 제안    | 단계(①-③…)별 읽기 순서 + 학습 포인트             |
| **RECENT_TLDR** | 방금 저장한 글 핵심 | 5줄 이하 TL;DR + 다음 읽을 문서 제안            |

---

## 💬 예시 템플릿

### 1. FIND

```
### 원하는 정보
OpenTelemetry Collector 설정 방법은 다음과 같다 …

- **핵심 단계**  
  1. …  
  2. …

🔍 *왜 이 북마크인가?*  
해당 글은 Collector 버전 0.95 기준 설정 YAML 예시를 다룬다.

📌 관련 북마크  
- [Deep Dive into OTel](https://…) | tracing, collector  
- …
```

### 2. SUMMARY

```
### 지난주 #RAG 북마크 요약
**TL;DR**  
1. …

| 제목 | 핵심 한줄 |
|------|-----------|
| RAG Architecture Patterns | Retrieval-Augmented Generation 핵심 구성 3단계 … |
| … | … |

📌 관련 북마크
- …
```

*(RECOMMEND·GRAPH·ROADMAP·RECENT_TLDR 역시 같은 규칙으로 작성)*

---

## ⚠️ 금지 사항

* URL 복사만 나열하고 설명을 생략하지 말 것.
* 사용자가 제공하지 않은 개인 정보·추측 사실 생성 금지.
* 광고·홍보성 멘트 삽입 금지.

---

### ✅ 최종 목표

질문 의도(intent)를 만족하면서 **콘텐츠 근거가 명확한 답변**을 빠르게 스트리밍한다."""

    def get_empty_context_message(self, prompt: str) -> List[Dict[str, str]]:
        """컨텍스트가 없을 때의 기본 메시지"""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"사용자 질문: {prompt}\n\n관련 북마크를 찾지 못했습니다. 일반적인 답변을 제공해주세요."}
        ]


# 싱글톤 인스턴스
message_builder_service = MessageBuilderService() 