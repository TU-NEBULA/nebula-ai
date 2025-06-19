# 📁 테스트 데이터 디렉토리

이 디렉토리는 북마크 저장 시스템 테스트에 사용되는 다양한 테스트 데이터를 포함합니다.

## 📂 디렉토리 구조

```
tests/data/
├── README.md           # 이 파일
├── html/               # 테스트용 HTML 파일들
│   ├── ai_machine_learning.html    # AI/ML 관련 콘텐츠
│   ├── web_development.html        # 웹 개발 관련 콘텐츠
│   ├── data_science.html           # 데이터 사이언스 관련 콘텐츠
│   └── blockchain_crypto.html      # 블록체인/암호화폐 관련 콘텐츠
├── samples/            # 샘플 데이터 파일들
└── fixtures/           # 테스트 픽스처 데이터
```

## 🎯 HTML 테스트 파일들

### 1. ai_machine_learning.html
- **주제**: 인공지능과 머신러닝 기초
- **특징**: 기본적인 HTML 구조, 목록과 단락
- **용도**: 기본적인 텍스트 추출 테스트

### 2. web_development.html  
- **주제**: 웹 개발 가이드
- **특징**: 메타 태그, 구조화된 콘텐츠
- **용도**: 메타데이터 추출 및 구조화된 콘텐츠 테스트

### 3. data_science.html
- **주제**: 데이터 사이언스 입문
- **특징**: 복합적인 HTML 구조 (header, nav, section, aside)
- **용도**: 복잡한 HTML 구조에서의 텍스트 추출 테스트

### 4. blockchain_crypto.html
- **주제**: 블록체인과 암호화폐
- **특징**: 테이블, 이모지, 다양한 HTML 요소
- **용도**: 특수 문자 및 복합 요소 처리 테스트

## 🧪 테스트에서의 사용법

### 수동 테스트
```python
# tests/manual/consumer_test.py에서 사용
test_data = {
    "s3Key": "tests/data/html/ai_machine_learning.html",
    "title": "AI와 머신러닝 기초",
    # ... 기타 필드
}
```

### 성능 테스트
```python
# tests/performance/bookmark_performance_test.py에서 사용
html_files = [
    "tests/data/html/ai_machine_learning.html",
    "tests/data/html/web_development.html", 
    "tests/data/html/data_science.html",
    "tests/data/html/blockchain_crypto.html"
]
```

### 통합 테스트
```python
# tests/integration/test_bookmark_flow_integration.py에서 사용
@pytest.fixture
def sample_html_content():
    with open("tests/data/html/ai_machine_learning.html", "r") as f:
        return f.read()
```

## 📊 데이터 특성

| 파일명 | 크기(추정) | 주요 키워드 | HTML 복잡도 |
|--------|------------|-------------|-------------|
| ai_machine_learning.html | ~1KB | AI, 머신러닝, 딥러닝 | 낮음 |
| web_development.html | ~2KB | 웹개발, 프론트엔드, 백엔드 | 중간 |
| data_science.html | ~3KB | 데이터사이언스, 분석, 파이썬 | 높음 |
| blockchain_crypto.html | ~4KB | 블록체인, 암호화폐, 비트코인 | 매우 높음 |

## 🔄 데이터 업데이트

새로운 테스트 데이터가 필요한 경우:

1. **HTML 파일 추가**: `tests/data/html/` 디렉토리에 추가
2. **README 업데이트**: 새 파일에 대한 설명 추가
3. **테스트 코드 수정**: 필요시 테스트 스크립트에서 새 파일 참조

## 🎨 테스트 데이터 생성 가이드

새로운 HTML 테스트 파일 생성 시 고려사항:

### 필수 요소
- [ ] `<!DOCTYPE html>` 선언
- [ ] `<title>` 태그 (의미있는 제목)
- [ ] `<meta charset="utf-8">` 설정
- [ ] 구조화된 콘텐츠 (h1, h2, p, ul 등)

### 다양성 확보
- [ ] 다른 주제/도메인 선택
- [ ] 다른 HTML 구조 사용
- [ ] 다양한 텍스트 길이
- [ ] 특수 문자/이모지 포함 (선택사항)

### 실용성
- [ ] 실제 웹 페이지와 유사한 구조
- [ ] 의미있는 콘텐츠 (랜덤 텍스트 지양)
- [ ] 적절한 파일 크기 (1-5KB 권장)

## 🧹 정리 명령어

```bash
# 테스트 데이터 디렉토리 정리
find tests/data -name "*.html" -exec wc -l {} + | sort -n

# HTML 파일 유효성 검사 (선택사항)
for file in tests/data/html/*.html; do
    echo "Checking $file..."
    # HTML 검증 도구 실행
done
```

## 📝 주의사항

- 테스트 데이터는 실제 개인정보나 민감한 정보를 포함하지 않아야 합니다
- 저작권이 있는 콘텐츠는 피하고, 교육/테스트 목적의 콘텐츠만 사용하세요
- 파일 크기는 적절히 유지하여 테스트 성능에 영향을 주지 않도록 하세요
- 모든 HTML 파일은 UTF-8 인코딩을 사용해야 합니다 