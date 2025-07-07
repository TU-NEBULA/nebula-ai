#!/usr/bin/env bash

# RabbitMQ 부하 테스트 실행 스크립트 (기존 서비스 연결)
# 사용법: ./scripts/run_locust_rmq.sh [users] [spawn_rate] [run_time]

set -e

# 기본값 설정
USERS=${1:-500}
SPAWN_RATE=${2:-50}
RUN_TIME=${3:-5m}
AMQP_URL=${AMQP_URL:-amqp://guest:guest@host.docker.internal:5672/%2f}
OUTPUT_DIR=${OUTPUT_DIR:-reports}

# 출력 디렉터리 생성
mkdir -p $OUTPUT_DIR

echo "🐰 RabbitMQ 부하 테스트 시작 (기존 서비스 연결)"
echo "   사용자 수: $USERS"
echo "   스폰 속도: $SPAWN_RATE/s"
echo "   실행 시간: $RUN_TIME"
echo "   AMQP URL: $AMQP_URL"
echo "   결과 저장: $OUTPUT_DIR/rmq_load_test_*"
echo ""
echo "📋 전제조건: 기존 RabbitMQ 서비스가 실행 중이어야 합니다"
echo "   - RabbitMQ: localhost:5672"
echo "   - Management UI: http://localhost:15672"
echo "   - 확인: curl -u guest:guest http://localhost:15672/api/overview"
echo ""

# 기존 RabbitMQ 서비스 상태 확인
echo "🔍 기존 RabbitMQ 서비스 상태 확인 중..."
if curl -s -u guest:guest http://localhost:15672/api/overview > /dev/null; then
    echo "✅ RabbitMQ 연결 확인됨"
else
    echo "❌ RabbitMQ에 연결할 수 없습니다"
    echo "   기존 서비스를 먼저 실행해주세요: docker compose up -d"
    exit 1
fi

# Docker Compose를 사용한 headless 실행
USERS=$USERS SPAWN_RATE=$SPAWN_RATE RUN_TIME=$RUN_TIME \
docker compose -f docker/locust/docker-compose.locust.yml \
  run --rm locust-rmq-headless

echo ""
echo "✅ RabbitMQ 부하 테스트 완료!"
echo "📊 결과 파일:"
ls -la $OUTPUT_DIR/rmq_load_test_* 2>/dev/null || echo "   결과 파일을 찾을 수 없습니다."

# CSV 결과 간단 요약 (결과 파일이 있는 경우)
if [ -f "$OUTPUT_DIR/rmq_load_test_stats.csv" ]; then
    echo ""
    echo "📈 간단 요약:"
    echo "   평균 발행시간: $(tail -n +2 $OUTPUT_DIR/rmq_load_test_stats.csv | awk -F',' '{sum+=$6; count++} END {printf "%.2f ms", sum/count}')"
    echo "   총 메시지 수: $(tail -n +2 $OUTPUT_DIR/rmq_load_test_stats.csv | awk -F',' '{sum+=$2} END {print sum}')"
    echo "   실패 수: $(tail -n +2 $OUTPUT_DIR/rmq_load_test_stats.csv | awk -F',' '{sum+=$4} END {print sum}')"
    echo ""
    echo "💡 RabbitMQ Management UI에서 큐 상태를 확인하세요:"
    echo "   http://localhost:15672 (guest/guest)"
fi 