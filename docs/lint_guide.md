# 파일별 린트 적용 가이드

Nebula AI 프로젝트에서 개별 파일에 대해 린트를 적용하는 방법을 설명합니다.

## 🎯 개요

대규모 프로젝트에서 전체 파일에 린트를 적용하면 시간이 오래 걸리고, 수정해야 할 이슈가 너무 많을 수 있습니다. 
파일별 린트 기능을 통해 작업 중인 특정 파일에만 집중해서 코드 품질을 개선할 수 있습니다.

## 🛠️ 사용 가능한 도구

### 1. Makefile 명령어 (추천)

```bash
# 도움말 보기
make help-lint

# 특정 파일 린트 검사만 수행
make lint-file FILE=app/main.py

# 특정 파일 자동 수정 후 린트 검사
make lint-fix-file FILE=app/main.py
```

### 2. 전용 스크립트 (고급 기능)

```bash
# 기본 사용법 (검사만)
./scripts/lint_file.sh app/main.py

# 자동 수정 후 검사
./scripts/lint_file.sh --fix app/main.py

# 검사만 명시적으로 지정
./scripts/lint_file.sh --check-only app/main.py

# 도움말
./scripts/lint_file.sh --help
```

### 3. 직접 명령어

```bash
# pylint만 실행
pylint app/main.py

# pylint 설정 파일 사용 (있는 경우)
pylint app/main.py --rcfile=.pylintrc

# 자동 수정 도구들 순차 실행
autopep8 --in-place --aggressive --aggressive app/main.py
isort app/main.py
black app/main.py
pylint app/main.py
```

## 🔧 지원하는 도구들

| 도구 | 용도 | 설치 명령어 |
|------|------|-------------|
| **pylint** | 코드 품질 검사 (필수) | `pip install pylint` |
| **autopep8** | PEP8 준수를 위한 자동 수정 | `pip install autopep8` |
| **isort** | import 구문 정렬 | `pip install isort` |
| **black** | 코드 포매팅 | `pip install black` |
| **mypy** | 타입 검사 (선택적) | `pip install mypy` |

## 📋 작업 흐름 예시

### 단계별 파일 수정 과정

1. **현재 상태 확인**
   ```bash
   make lint-file FILE=app/main.py
   ```

2. **자동 수정 적용**
   ```bash
   make lint-fix-file FILE=app/main.py
   ```

3. **수동 수정이 필요한 부분 확인**
   ```bash
   make lint-file FILE=app/main.py
   ```

4. **최종 확인**
   ```bash
   ./scripts/lint_file.sh --check-only app/main.py
   ```

### 일괄 처리 방법

여러 파일을 연속으로 처리하려면:

```bash
# 스크립트 사용 (권장)
for file in app/main.py app/models/user.py app/services/user_service.py; do
    echo "처리 중: $file"
    ./scripts/lint_file.sh --fix "$file"
done

# 또는 Make 사용
for file in app/main.py app/models/user.py app/services/user_service.py; do
    make lint-fix-file FILE="$file"
done
```

## ⚠️ 주의사항

### 1. 백업 권장
자동 수정 기능(`--fix`, `lint-fix-file`)을 사용하기 전에는 중요한 변경사항을 커밋하거나 백업해두세요.

### 2. 점진적 적용
한 번에 모든 파일을 수정하기보다는 작업 중인 파일부터 점진적으로 적용하는 것을 권장합니다.

### 3. 팀 규칙 준수
`.pylintrc` 파일이 있다면 팀에서 정한 규칙을 따르므로, 개인적으로 pylint 설정을 변경하지 마세요.

## 🚨 문제 해결

### pylint 관련 오류
```bash
# pylint 설치 확인
which pylint
pip install pylint

# pylint 설정 파일 확인
ls -la .pylintrc
```

### 권한 오류
```bash
# 스크립트 실행 권한 부여
chmod +x scripts/lint_file.sh
```

### 도구 설치
```bash
# 개발 환경 전체 설치
pipenv install --dev

# 또는 개별 설치
pip install pylint autopep8 isort black mypy
```

## 📊 성능 비교

| 방법 | 속도 | 기능 | 사용 편의성 |
|------|------|------|-------------|
| `make lint-file` | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| `./scripts/lint_file.sh` | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 직접 명령어 | ⭐⭐⭐ | ⭐ | ⭐ |

## 🔗 관련 문서

- [전체 프로젝트 린트 가이드](../README.md#코드-품질)
- [개발 환경 설정](../README.md#개발-환경-설정)
- [Makefile 명령어 참조](../Makefile)

---

💡 **팁**: 개발 중에는 `./scripts/lint_file.sh --fix 파일명` 명령어를 자주 사용하여 코드 품질을 지속적으로 유지할 수 있습니다.