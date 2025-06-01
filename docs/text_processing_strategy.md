# 텍스트 처리 전략 가이드

## 📋 개요

Nebula AI 프로젝트에서 텍스트 분할과 키워드 추출을 언제, 어떻게 사용해야 하는지에 대한 최적화된 전략을 설명합니다.

## 🎯 핵심 원칙

### 1. **키워드 추출**: 텍스트 분할 안 함
- **이유**: 문서 전체의 맥락을 고려하여 더 의미있는 키워드 추출
- **방법**: 형태소 분석기 기반 명사 추출 + 빈도 분석
- **예외**: 10,000자 이상의 매우 긴 텍스트만 청크별 키워드 추출 후 병합

### 2. **RAG(벡터 검색)**: 텍스트 분할 필수
- **이유**: 검색 성능과 임베딩 품질 최적화
- **방법**: RecursiveCharacterTextSplitter 사용
- **특징**: 사용자 키워드/메모를 메타데이터로 포함

## 🔍 사용 사례별 전략

### Case 1: 일반적인 키워드 추출
```python
from app.utils.text_processing import extract_keywords

# 웹페이지나 문서에서 키워드 추출
keywords = extract_keywords(text, max_keywords=20)
```

**특징:**
- 전체 텍스트를 한번에 분석
- 형태소 분석기로 명사만 추출 (한국어: Okt, 영어: NLTK)
- 596개 한국어 + NLTK 영어 불용어 제거
- 문서 전체 맥락 고려

### Case 2: 매우 긴 텍스트의 키워드 추출
```python
from app.utils.text_processing import extract_keywords_from_chunks

# 10,000자 이상의 긴 텍스트
keywords = extract_keywords_from_chunks(text, max_keywords=20, chunk_size=2000)
```

**특징:**
- 2000자 단위로 분할 (키워드 추출용이므로 큰 사이즈)
- 400자 오버랩 (키워드 연속성 보장)
- 각 청크에서 키워드 추출 후 빈도순 병합

### Case 3: RAG용 텍스트 분할
```python
from app.utils.text_processing import extract_text_chunks_for_rag

# RAG 검색을 위한 텍스트 분할
chunks = extract_text_chunks_for_rag(text, chunk_size=1000, chunk_overlap=200)
```

**특징:**
- 1000자 단위 분할 (검색 최적화)
- 200자 오버랩 (맥락 연속성)
- 100자 미만 청크 제거
- 독립적 검색 가능한 단위

### Case 4: 북마크 저장 (RAG + 사용자 데이터)
```python
from app.utils.text_processing import prepare_content_for_rag

# 사용자 키워드/메모 포함한 RAG 준비
rag_chunks = prepare_content_for_rag(
    text=content,
    keywords=user_keywords,
    memo=user_memo,
    summary=summary
)
```

**특징:**
- RAG 최적화 분할
- 각 청크에 메타데이터 포함
- 청크별 키워드도 추가 추출
- 사용자 컨텍스트 보존

## 🚀 북마크 저장 최적화 전략

### 다층 저장 구조

1. **콘텐츠 청크**: 원본 내용을 RAG 최적화 크기로 분할
2. **사용자 메모**: 별도 문서로 저장 (높은 검색 우선순위)
3. **요약 정보**: 별도 문서로 저장 (개요 파악용)

### 키워드 통합 전략

```python
# 사용자 선택 키워드 + 자동 추출 키워드
extracted_keywords = extract_keywords(content, max_keywords=10)
combined_keywords = list(set(user_keywords + extracted_keywords))
```

### 메타데이터 구조

```python
{
    "chunk_type": "content|user_memo|summary",
    "user_selected_keywords": [...],
    "extracted_keywords": [...],
    "chunk_keywords": [...],
    "user_memo": "...",
    "s3_key": "..."
}
```

## 📊 성능 비교

### 키워드 추출 성능
| 방식 | 텍스트 길이 | 처리 시간 | 품질 |
|------|------------|----------|------|
| 전체 분석 | < 10K자 | 빠름 | 높음 |
| 청크별 분석 | > 10K자 | 보통 | 보통 |

### RAG 검색 성능
| 청크 크기 | 검색 정확도 | 응답 속도 | 메모리 사용 |
|----------|------------|----------|------------|
| 500자 | 높음 | 빠름 | 높음 |
| 1000자 | 최적 | 최적 | 최적 |
| 2000자 | 낮음 | 느림 | 낮음 |

## 🛠️ 실제 구현 예시

### NLP 데이터 추출기에서의 키워드 추출

```python
class NebulaNLPExtractor:
    async def _extract_keywords_tfidf(self, text: str, max_keywords: int = 3) -> List[str]:
        """키워드 추출 - 텍스트 분할 없이 전체 분석"""
        return extract_keywords(text, max_keywords)
```

**장점:**
- 전체 문서 맥락 고려
- 더 의미있는 키워드 추출
- 처리 속도 빠름

### 북마크 저장에서의 RAG 최적화

```python
def _save_bookmark_logic(...):
    # 1. RAG 최적화 청크 생성
    rag_chunks = prepare_content_for_rag(text, keywords, memo, summary)
    
    # 2. 콘텐츠 청크 저장
    for chunk_data in rag_chunks:
        await vector_service.save_document(...)
    
    # 3. 메모 별도 저장 (높은 우선순위)
    if memo:
        await vector_service.save_document(source_type="bookmark_memo", ...)
    
    # 4. 요약 별도 저장 (개요 파악용)  
    if summary:
        await vector_service.save_document(source_type="bookmark_summary", ...)
```

**장점:**
- 검색 정확도 향상
- 사용자 컨텍스트 보존
- RAG 응답 품질 개선

## 📝 권장사항

### DO ✅

1. **키워드 추출**: 전체 텍스트 분석 우선
2. **RAG**: 1000자/200자 오버랩 청크 사용
3. **사용자 데이터**: 별도 문서로 저장
4. **메타데이터**: 풍부한 컨텍스트 정보 포함

### DON'T ❌

1. **키워드 추출에 작은 청크 사용** (맥락 손실)
2. **RAG에 너무 큰 청크 사용** (검색 성능 저하)
3. **사용자 메모 무시** (개인화 손실)
4. **메타데이터 부족** (검색 품질 저하)

## 🎯 결론

- **키워드 추출**: 전체 텍스트 분석이 최적
- **RAG 검색**: 적절한 청크 분할이 필수
- **사용자 데이터**: 별도 저장으로 우선순위 부여
- **북마크 시스템**: 다층 구조로 검색 품질 극대화

이 전략을 통해 Nebula AI는 정확한 키워드 추출과 효과적인 RAG 검색을 동시에 제공할 수 있습니다. 