#!/usr/bin/env python3
"""
모니터링 시스템 검증 스크립트

이 스크립트는 Nebula AI 애플리케이션의 모니터링 시스템이 
올바르게 작동하는지 확인하기 위한 테스트를 수행합니다.
"""

import time
import requests
import asyncio
import json
from typing import Dict, Any
from loguru import logger


class MonitoringTester:
    """모니터링 시스템 테스트 클래스"""
    
    def __init__(self):
        self.app_url = "http://localhost:8001"
        self.prometheus_url = "http://localhost:9090"
        self.grafana_url = "http://localhost:3000"
        
    def test_application_health(self) -> bool:
        """애플리케이션 헬스체크"""
        logger.info("🏥 애플리케이션 헬스체크 테스트...")
        try:
            response = requests.get(f"{self.app_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                logger.success(f"✅ 애플리케이션 정상 작동: {health_data}")
                return True
            else:
                logger.error(f"❌ 헬스체크 실패: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 애플리케이션 연결 실패: {e}")
            return False
    
    def test_metrics_endpoint(self) -> bool:
        """메트릭 엔드포인트 테스트"""
        logger.info("📊 메트릭 엔드포인트 테스트...")
        try:
            response = requests.get(f"{self.app_url}/metrics", timeout=10)
            if response.status_code == 200:
                metrics_text = response.text
                metric_count = len([line for line in metrics_text.split('\n') 
                                 if line and not line.startswith('#')])
                logger.success(f"✅ 메트릭 수집 정상: {metric_count}개 메트릭")
                
                # 주요 메트릭 확인
                required_metrics = [
                    'http_requests_total',
                    'http_request_duration_seconds',
                    'memory_usage_bytes',
                    'cpu_usage_percent'
                ]
                
                for metric in required_metrics:
                    if metric in metrics_text:
                        logger.info(f"  ✓ {metric} 메트릭 확인됨")
                    else:
                        logger.warning(f"  ⚠️ {metric} 메트릭 누락")
                
                return True
            else:
                logger.error(f"❌ 메트릭 엔드포인트 실패: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 메트릭 엔드포인트 연결 실패: {e}")
            return False
    
    def test_prometheus_connection(self) -> bool:
        """프로메테우스 연결 테스트"""
        logger.info("🔍 프로메테우스 연결 테스트...")
        try:
            # 프로메테우스 상태 확인
            response = requests.get(f"{self.prometheus_url}/api/v1/status/config", timeout=10)
            if response.status_code == 200:
                logger.success("✅ 프로메테우스 연결 정상")
                
                # 타겟 상태 확인
                targets_response = requests.get(f"{self.prometheus_url}/api/v1/targets", timeout=10)
                if targets_response.status_code == 200:
                    targets_data = targets_response.json()
                    active_targets = targets_data.get('data', {}).get('activeTargets', [])
                    
                    for target in active_targets:
                        job = target.get('labels', {}).get('job', 'unknown')
                        health = target.get('health', 'unknown')
                        logger.info(f"  🎯 {job}: {health}")
                
                return True
            else:
                logger.error(f"❌ 프로메테우스 연결 실패: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 프로메테우스 연결 실패: {e}")
            return False
    
    def test_grafana_connection(self) -> bool:
        """그라파나 연결 테스트"""
        logger.info("📈 그라파나 연결 테스트...")
        try:
            response = requests.get(f"{self.grafana_url}/api/health", timeout=10)
            if response.status_code == 200:
                logger.success("✅ 그라파나 연결 정상")
                return True
            else:
                logger.error(f"❌ 그라파나 연결 실패: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 그라파나 연결 실패: {e}")
            return False
    
    def generate_test_traffic(self) -> None:
        """테스트 트래픽 생성"""
        logger.info("🚦 테스트 트래픽 생성 중...")
        
        endpoints = [
            "/",
            "/health",
            "/docs",
            "/api/v1/profiles/health-check"
        ]
        
        for i in range(50):
            for endpoint in endpoints:
                try:
                    response = requests.get(f"{self.app_url}{endpoint}", timeout=5)
                    logger.debug(f"Request {i+1}: {endpoint} -> {response.status_code}")
                except Exception as e:
                    logger.debug(f"Request {i+1}: {endpoint} -> Error: {e}")
                
                time.sleep(0.1)  # 100ms 간격
        
        logger.success("✅ 테스트 트래픽 생성 완료")
    
    def check_metrics_after_traffic(self) -> bool:
        """트래픽 생성 후 메트릭 확인"""
        logger.info("📊 트래픽 생성 후 메트릭 변화 확인...")
        
        # 잠시 대기하여 메트릭이 수집되도록 함
        time.sleep(5)
        
        try:
            # 프로메테우스에서 HTTP 요청 메트릭 조회
            query = "sum(rate(http_requests_total[1m]))"
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('data', {}).get('result', [])
                
                if result:
                    value = float(result[0]['value'][1])
                    logger.success(f"✅ HTTP 요청률: {value:.2f} req/sec")
                    return True
                else:
                    logger.warning("⚠️ HTTP 요청 메트릭 데이터 없음")
                    return False
            else:
                logger.error(f"❌ 메트릭 조회 실패: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 메트릭 조회 실패: {e}")
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """모든 테스트 실행"""
        logger.info("🧪 모니터링 시스템 전체 테스트 시작...")
        
        results = {}
        
        # 1. 애플리케이션 헬스체크
        results['app_health'] = self.test_application_health()
        
        # 2. 메트릭 엔드포인트 테스트
        results['metrics_endpoint'] = self.test_metrics_endpoint()
        
        # 3. 프로메테우스 연결 테스트
        results['prometheus'] = self.test_prometheus_connection()
        
        # 4. 그라파나 연결 테스트
        results['grafana'] = self.test_grafana_connection()
        
        # 5. 테스트 트래픽 생성
        if results['app_health']:
            self.generate_test_traffic()
            results['traffic_generation'] = True
            
            # 6. 메트릭 변화 확인
            results['metrics_after_traffic'] = self.check_metrics_after_traffic()
        else:
            results['traffic_generation'] = False
            results['metrics_after_traffic'] = False
        
        # 결과 요약
        logger.info("\n" + "="*50)
        logger.info("📋 테스트 결과 요약:")
        logger.info("="*50)
        
        for test_name, result in results.items():
            status = "✅ 통과" if result else "❌ 실패"
            test_description = {
                'app_health': '애플리케이션 헬스체크',
                'metrics_endpoint': '메트릭 엔드포인트',
                'prometheus': '프로메테우스 연결',
                'grafana': '그라파나 연결',
                'traffic_generation': '테스트 트래픽 생성',
                'metrics_after_traffic': '메트릭 수집 확인'
            }.get(test_name, test_name)
            
            logger.info(f"{test_description}: {status}")
        
        success_count = sum(results.values())
        total_count = len(results)
        logger.info(f"\n총 {total_count}개 테스트 중 {success_count}개 성공")
        
        if success_count == total_count:
            logger.success("🎉 모든 테스트가 성공했습니다!")
        else:
            logger.warning(f"⚠️ {total_count - success_count}개 테스트가 실패했습니다.")
        
        return results


def main():
    """메인 함수"""
    logger.add("logs/monitoring_test.log", rotation="1 day", level="DEBUG")
    
    tester = MonitoringTester()
    results = tester.run_all_tests()
    
    # 종료 코드 설정 (모든 테스트 성공시 0, 실패시 1)
    exit_code = 0 if all(results.values()) else 1
    exit(exit_code)


if __name__ == "__main__":
    main() 