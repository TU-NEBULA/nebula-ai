#!/bin/bash

# ============================================================================
# Nebula AI - 파일별 린트 적용 스크립트
# ============================================================================

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 사용법 출력
usage() {
    echo -e "${BLUE}사용법:${NC}"
    echo "  $0 [옵션] <파일경로>"
    echo ""
    echo -e "${BLUE}옵션:${NC}"
    echo "  -c, --check-only    린트 검사만 수행 (수정하지 않음)"
    echo "  -f, --fix           자동 수정 후 린트 검사"
    echo "  -h, --help          도움말 표시"
    echo ""
    echo -e "${BLUE}예시:${NC}"
    echo "  $0 app/main.py                    # 기본 린트 검사"
    echo "  $0 --fix app/main.py             # 자동 수정 후 린트 검사"
    echo "  $0 --check-only app/main.py      # 검사만 수행"
    echo ""
    echo -e "${BLUE}지원하는 도구들:${NC}"
    echo "  - pylint: 코드 품질 검사"
    echo "  - autopep8: PEP8 준수를 위한 자동 수정"
    echo "  - isort: import 구문 정렬"
    echo "  - black: 코드 포매팅"
    echo "  - mypy: 타입 검사 (선택적)"
}

# 도구 존재 여부 확인
check_tool() {
    if command -v "$1" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 린트 검사만 수행
lint_check() {
    local file="$1"
    echo -e "${BLUE}🔍 $file 린트 검사 중...${NC}"
    
    # pylint 검사
    if check_tool "pylint"; then
        if [ -f ".pylintrc" ]; then
            pylint "$file" --rcfile=.pylintrc
        else
            pylint "$file"
        fi
    else
        echo -e "${RED}❌ pylint가 설치되지 않았습니다${NC}"
        exit 1
    fi
    
    # mypy 검사 (선택적)
    if check_tool "mypy"; then
        echo -e "${BLUE}🔍 타입 검사 중...${NC}"
        mypy "$file" || echo -e "${YELLOW}⚠️  mypy 검사에서 일부 이슈가 발견되었습니다${NC}"
    fi
}

# 자동 수정 후 린트 검사
lint_fix() {
    local file="$1"
    echo -e "${BLUE}🔧 $file 자동 수정 중...${NC}"
    
    # 1. autopep8로 PEP8 준수 수정
    if check_tool "autopep8"; then
        echo -e "${GREEN}✅ autopep8 적용 중...${NC}"
        autopep8 --in-place --aggressive --aggressive "$file"
    else
        echo -e "${YELLOW}⚠️  autopep8가 설치되지 않음 - 건너뜀${NC}"
    fi
    
    # 2. isort로 import 정렬
    if check_tool "isort"; then
        echo -e "${GREEN}✅ import 정렬 중...${NC}"
        isort "$file"
    else
        echo -e "${YELLOW}⚠️  isort가 설치되지 않음 - 건너뜀${NC}"
    fi
    
    # 3. black으로 포매팅
    if check_tool "black"; then
        echo -e "${GREEN}✅ black 포매팅 적용 중...${NC}"
        black "$file"
    else
        echo -e "${YELLOW}⚠️  black이 설치되지 않음 - 건너뜀${NC}"
    fi
    
    # 4. 최종 pylint 검사
    echo -e "${BLUE}🔍 최종 린트 검사...${NC}"
    lint_check "$file" || echo -e "${YELLOW}⚠️  일부 린트 이슈가 남아있습니다${NC}"
}

# 메인 로직
main() {
    local check_only=false
    local fix_mode=false
    local file=""
    
    # 인자 파싱
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--check-only)
                check_only=true
                shift
                ;;
            -f|--fix)
                fix_mode=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            -*)
                echo -e "${RED}❌ 알 수 없는 옵션: $1${NC}"
                usage
                exit 1
                ;;
            *)
                file="$1"
                shift
                ;;
        esac
    done
    
    # 파일 경로 검증
    if [ -z "$file" ]; then
        echo -e "${RED}❌ 파일 경로를 지정해주세요${NC}"
        usage
        exit 1
    fi
    
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ 파일을 찾을 수 없습니다: $file${NC}"
        exit 1
    fi
    
    if [[ "$file" != *.py ]]; then
        echo -e "${RED}❌ Python 파일(.py)만 지원됩니다: $file${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}🚀 파일별 린트 적용 시작: $file${NC}"
    echo "================================================"
    
    # 실행 모드에 따른 처리
    if [ "$check_only" = true ]; then
        lint_check "$file"
    elif [ "$fix_mode" = true ]; then
        lint_fix "$file"
    else
        # 기본값: 검사만 수행
        lint_check "$file"
    fi
    
    echo "================================================"
    echo -e "${GREEN}✅ 완료!${NC}"
}

# 스크립트 실행
main "$@" 