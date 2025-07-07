#!/usr/bin/env bash

# 프로필 API 부하 테스트 실행 스크립트 (기존 서비스 연결)
# 사용법: ./scripts/run_locust_profile.sh [users] [spawn_rate] [run_time]

set -e

# 기본값 설정
USERS=${1:-100}
SPAWN_RATE=${2:-10}
RUN_TIME=${3:-5m}
HOST=${HOST:-http://host.docker.internal:8000}
OUTPUT_DIR=${OUTPUT_DIR:-reports}

# 출력 디렉터리 생성
mkdir -p $OUTPUT_DIR

echo "👤 프로필 API 부하 테스트 시작 (기존 서비스 연결)"
echo "   사용자 수: $USERS"
echo "   스폰 속도: $SPAWN_RATE/s"
echo "   실행 시간: $RUN_TIME"
echo "   대상 호스트: $HOST"
echo "   결과 저장: $OUTPUT_DIR/profile_load_test_*"
echo ""
echo "📋 전제조건: 기존 Nebula AI 서비스가 실행 중이어야 합니다"
echo "   - API 서버: http://localhost:8000"
echo "   - 프로필 엔드포인트: /profile/{user_id}"
echo "   - 추천 엔드포인트: /recommendations/{user_id}"
echo "   - 분석 엔드포인트: /analytics/{user_id}"
echo ""

# 기존 서비스 상태 확인
echo "🔍 기존 서비스 상태 확인 중..."
if curl -s http://localhost:8000/docs > /dev/null; then
    echo "✅ API 서버 연결 확인됨"
else
    echo "❌ API 서버에 연결할 수 없습니다"
    echo "   기존 서비스를 먼저 실행해주세요: docker compose up -d"
    exit 1
fi

# Docker Compose를 사용한 headless 실행
USERS=$USERS SPAWN_RATE=$SPAWN_RATE RUN_TIME=$RUN_TIME \
docker compose -f docker/locust/docker-compose.locust.yml \
  run --rm locust-profile-headless

echo ""
echo "✅ 프로필 API 부하 테스트 완료!"
echo "📊 결과 파일:"
ls -la $OUTPUT_DIR/profile_load_test_* 2>/dev/null || echo "   결과 파일을 찾을 수 없습니다."

# CSV 결과 간단 요약 (결과 파일이 있는 경우)
if [ -f "$OUTPUT_DIR/profile_load_test_stats.csv" ]; then
    echo ""
    echo "📈 간단 요약:"
    echo "   평균 응답시간: $(tail -n +2 $OUTPUT_DIR/profile_load_test_stats.csv | awk -F',' '{sum+=$6; count++} END {printf "%.2f ms", sum/count}')"
    echo "   총 요청 수: $(tail -n +2 $OUTPUT_DIR/profile_load_test_stats.csv | awk -F',' '{sum+=$2} END {print sum}')"
    echo "   실패 수: $(tail -n +2 $OUTPUT_DIR/profile_load_test_stats.csv | awk -F',' '{sum+=$4} END {print sum}')"
    echo ""
    echo "💡 상세 분석을 위해 다음 엔드포인트별 결과를 확인하세요:"
    echo "   - /profile/{user_id}: 프로필 조회 성능"
    echo "   - /recommendations/{user_id}: 추천 엔진 성능"
    echo "   - /analytics/{user_id}: 분석 데이터 성능"
fi 