# 테스트 가이드

이 문서는 Nebula AI 프로젝트의 테스트 구조와 실행 방법을 설명합니다.

## 새로 추가된 기능 테스트

### 🔍 형태소 분석기 기반 키워드 추출 테스트

프로젝트에 새로 추가된 형태소 분석기를 사용한 키워드 추출 기능에 대한 포괄적인 테스트가 구현되었습니다.

#### 📁 테스트 파일 구조

```
tests/
├── utils/
│   ├── __init__.py
│   └── test_text_processing.py      # 텍스트 처리 유틸리티 테스트
└── tasks/
    └── test_data_extractor_nlp.py   # NLP 데이터 추출기 테스트
```

#### 🧪 테스트 커버리지

**텍스트 처리 유틸리티 (`test_text_processing.py`)**

1. **TestExtractKeywords**: 형태소 분석기 기반 키워드 추출
   - 한국어 명사 추출 (Okt 사용)
   - 영어 명사 추출 (NLTK pos_tag 사용)
   - 한영 혼합 텍스트 처리
   - 불용어 제거 (ko_stopwords.txt + NLTK stopwords)
   - 빈 텍스트 처리
   - 최대 키워드 수 제한
   - 형태소 분석기 오류 처리

2. **TestExtractMainText**: HTML 텍스트 추출
   - HTML에서 본문 텍스트 추출
   - 스크립트/스타일 태그 제거

3. **TestKoreanStopwords**: 한국어 불용어 처리
   - 불용어 파일 로드
   - 한국어/영어 불용어 제거

4. **TestTokenize**: 토큰화 기능
   - 한국어/영어 토큰화

5. **TestSplitSentences**: 문장 분리
   - 정규식 기반 문장 분리

6. **TestGenerateTextSummary**: 텍스트 요약
   - 추출식 요약 생성

7. **TestCalculateTextSimilarity**: 텍스트 유사도
   - Jaccard 유사도 계산

8. **TestIntegration**: 통합 테스트
   - 전체 키워드 추출 파이프라인
   - 다국어 처리 테스트

**NLP 데이터 추출기 (`test_data_extractor_nlp.py`)**

1. **TestNebulaNLPExtractor**: 개별 기능 테스트
   - 추출기 초기화
   - HTML 컨텐츠 가져오기
   - 텍스트 컨텐츠 추출
   - 키워드 추출 (형태소 분석기 적용)
   - 썸네일 생성
   - 이미지 추출
   - 제목/메타 설명 추출
   - 전체 처리 파이프라인
   - 오류 처리

2. **TestIntegrationNLPExtractor**: 통합 테스트
   - text_processing 유틸리티와의 통합
   - 한영 혼합 컨텐츠 처리
   - 형태소 분석기 품질 검증

#### 🏃‍♂️ 테스트 실행 방법

**전체 테스트 실행:**
```bash
python -m pytest tests/utils/test_text_processing.py tests/tasks/test_data_extractor_nlp.py -v
```

**텍스트 처리 유틸리티 테스트만 실행:**
```bash
python -m pytest tests/utils/test_text_processing.py -v
```

**NLP 데이터 추출기 테스트만 실행:**
```bash
python -m pytest tests/tasks/test_data_extractor_nlp.py -v
```

**특정 테스트 클래스 실행:**
```bash
python -m pytest tests/utils/test_text_processing.py::TestExtractKeywords -v
```

**커버리지 리포트와 함께 실행:**
```bash
python -m pytest tests/utils/test_text_processing.py tests/tasks/test_data_extractor_nlp.py \
    --cov=app.utils.text_processing \
    --cov=app.tasks.data_extractor_nlp \
    --cov-report=term-missing
```

#### 📊 현재 테스트 커버리지

- **app.tasks.data_extractor_nlp.py**: 90% 커버리지
- **app.utils.text_processing.py**: 76% 커버리지
- **전체**: 81% 커버리지

#### 🎯 테스트 핵심 기능

1. **형태소 분석기 검증**
   - 한국어: KoNLPy Okt를 사용한 명사 추출
   - 영어: NLTK pos_tag를 사용한 명사 추출 (NN, NNS, NNP, NNPS)

2. **불용어 처리 검증**
   - 한국어: ko_stopwords.txt (596개 불용어)
   - 영어: NLTK stopwords

3. **오류 처리 검증**
   - 형태소 분석기 실패 시 graceful degradation
   - 네트워크 오류 처리
   - 빈 입력 처리

4. **통합 테스트**
   - HTML → 텍스트 추출 → 키워드 추출 전체 파이프라인
   - 다국어 처리 검증

#### 🔧 테스트 설정

테스트 실행을 위해 다음 의존성이 필요합니다:

```bash
# NLTK 데이터 다운로드
python -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger'); nltk.download('averaged_perceptron_tagger_eng')"
```

#### 📝 테스트 작성 가이드

새로운 텍스트 처리 기능을 추가할 때:

1. `tests/utils/test_text_processing.py`에 해당 기능 테스트 추가
2. 성공/실패 케이스 모두 포함
3. 한국어/영어 처리 모두 테스트
4. 빈 입력 및 예외 상황 테스트
5. Mock을 사용한 외부 의존성 격리

새로운 NLP 추출 기능을 추가할 때:

1. `tests/tasks/test_data_extractor_nlp.py`에 해당 기능 테스트 추가
2. 개별 메서드 테스트와 통합 테스트 구분
3. Mock을 사용한 네트워크 호출 시뮬레이션
4. 오류 처리 시나리오 포함

#### 🚀 지속적 개선

- 커버리지 목표: 90% 이상
- 새로운 기능 추가 시 테스트 우선 작성 (TDD)
- 형태소 분석기 성능 벤치마크 테스트 추가 예정
- E2E 테스트 추가 계획 