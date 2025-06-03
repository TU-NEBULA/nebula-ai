#!/usr/bin/env python3
"""
북마크 저장 시스템 성능 테스트

대량 데이터 처리, 동시성, 메모리 사용량 등을 테스트합니다.
"""

import asyncio
import time
import sys
import json
import statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import psutil
import os

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.rabbit import get_rabbit_connection
from app.consumers.bookmark_save_rmq import on_bookmark_save
from tests.manual.data_helper import test_data_helper
import aio_pika


class PerformanceMonitor:
    """성능 모니터링 클래스"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
        self.process = psutil.Process(os.getpid())
    
    def start(self):
        """모니터링 시작"""
        self.start_time = time.time()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
    
    def stop(self):
        """모니터링 종료"""
        self.end_time = time.time()
        self.end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
    
    def get_results(self):
        """결과 반환"""
        return {
            "duration": self.end_time - self.start_time,
            "memory_start": self.start_memory,
            "memory_end": self.end_memory,
            "memory_diff": self.end_memory - self.start_memory
        }


def generate_test_data(count: int):
    """테스트용 북마크 데이터 생성 (데이터 헬퍼 사용)"""
    return test_data_helper.get_performance_test_data(count)


class MockIncomingMessage:
    """테스트용 Mock 메시지"""
    
    def __init__(self, payload: dict):
        self.body = json.dumps(payload).encode('utf-8')
    
    def process(self):
        class MockContext:
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        return MockContext()


async def test_consumer_performance(test_data: list):
    """Consumer 성능 테스트"""
    
    print("\n🚀 Consumer 성능 테스트")
    print("=" * 50)
    
    monitor = PerformanceMonitor()
    monitor.start()
    
    success_count = 0
    error_count = 0
    processing_times = []
    
    for i, data in enumerate(test_data):
        message = MockIncomingMessage(data)
        
        start_time = time.time()
        try:
            await on_bookmark_save(message)
            success_count += 1
        except Exception as e:
            error_count += 1
            print(f"❌ 오류 #{i}: {e}")
        
        processing_time = time.time() - start_time
        processing_times.append(processing_time)
        
        if (i + 1) % 10 == 0:
            print(f"📊 진행률: {i+1}/{len(test_data)} ({(i+1)/len(test_data)*100:.1f}%)")
    
    monitor.stop()
    results = monitor.get_results()
    
    # 통계 계산
    avg_time = statistics.mean(processing_times)
    median_time = statistics.median(processing_times)
    max_time = max(processing_times)
    min_time = min(processing_times)
    
    print(f"\n📈 Consumer 성능 결과:")
    print(f"   총 처리 시간: {results['duration']:.2f}초")
    print(f"   처리량: {len(test_data)/results['duration']:.2f} 메시지/초")
    print(f"   성공: {success_count}, 실패: {error_count}")
    print(f"   평균 처리 시간: {avg_time*1000:.2f}ms")
    print(f"   중간값 처리 시간: {median_time*1000:.2f}ms")
    print(f"   최대 처리 시간: {max_time*1000:.2f}ms")
    print(f"   최소 처리 시간: {min_time*1000:.2f}ms")
    print(f"   메모리 사용량: {results['memory_start']:.1f}MB → {results['memory_end']:.1f}MB (차이: {results['memory_diff']:+.1f}MB)")
    
    return {
        "type": "consumer",
        "total_time": results['duration'],
        "throughput": len(test_data)/results['duration'],
        "success_rate": success_count/len(test_data),
        "avg_processing_time": avg_time,
        "memory_usage": results['memory_diff']
    }


async def test_rabbitmq_performance(test_data: list):
    """RabbitMQ 메시지 전송 성능 테스트"""
    
    print("\n📨 RabbitMQ 성능 테스트")
    print("=" * 50)
    
    monitor = PerformanceMonitor()
    
    try:
        # RabbitMQ 연결
        connection = await get_rabbit_connection()
        channel = await connection.channel()
        
        queue_name = "nebula.bookmark.save"
        await channel.declare_queue(queue_name, durable=True)
        
        monitor.start()
        
        success_count = 0
        error_count = 0
        send_times = []
        
        for i, data in enumerate(test_data):
            start_time = time.time()
            
            try:
                message_body = json.dumps(data).encode('utf-8')
                message = aio_pika.Message(
                    message_body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                )
                
                await channel.default_exchange.publish(
                    message,
                    routing_key=queue_name
                )
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"❌ 전송 오류 #{i}: {e}")
            
            send_time = time.time() - start_time
            send_times.append(send_time)
            
            if (i + 1) % 10 == 0:
                print(f"📊 진행률: {i+1}/{len(test_data)} ({(i+1)/len(test_data)*100:.1f}%)")
        
        monitor.stop()
        await connection.close()
        
        results = monitor.get_results()
        
        # 통계 계산
        avg_time = statistics.mean(send_times)
        median_time = statistics.median(send_times)
        
        print(f"\n📈 RabbitMQ 성능 결과:")
        print(f"   총 전송 시간: {results['duration']:.2f}초")
        print(f"   전송량: {len(test_data)/results['duration']:.2f} 메시지/초")
        print(f"   성공: {success_count}, 실패: {error_count}")
        print(f"   평균 전송 시간: {avg_time*1000:.2f}ms")
        print(f"   중간값 전송 시간: {median_time*1000:.2f}ms")
        
        return {
            "type": "rabbitmq",
            "total_time": results['duration'],
            "throughput": len(test_data)/results['duration'],
            "success_rate": success_count/len(test_data),
            "avg_send_time": avg_time
        }
        
    except Exception as e:
        print(f"❌ RabbitMQ 연결 실패: {e}")
        return None


async def test_concurrent_processing(test_data: list, concurrency: int = 5):
    """동시 처리 성능 테스트"""
    
    print(f"\n⚡ 동시 처리 테스트 (동시성: {concurrency})")
    print("=" * 50)
    
    monitor = PerformanceMonitor()
    monitor.start()
    
    # 데이터를 청크로 분할
    chunk_size = len(test_data) // concurrency
    chunks = [test_data[i:i+chunk_size] for i in range(0, len(test_data), chunk_size)]
    
    async def process_chunk(chunk, chunk_id):
        """청크 처리 함수"""
        success = 0
        errors = 0
        
        for data in chunk:
            message = MockIncomingMessage(data)
            try:
                await on_bookmark_save(message)
                success += 1
            except Exception:
                errors += 1
        
        return {"chunk_id": chunk_id, "success": success, "errors": errors}
    
    # 동시 실행
    tasks = [process_chunk(chunk, i) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks)
    
    monitor.stop()
    perf_results = monitor.get_results()
    
    # 결과 집계
    total_success = sum(r["success"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    
    print(f"\n📈 동시 처리 결과:")
    print(f"   총 처리 시간: {perf_results['duration']:.2f}초")
    print(f"   처리량: {len(test_data)/perf_results['duration']:.2f} 메시지/초")
    print(f"   성공: {total_success}, 실패: {total_errors}")
    print(f"   동시성 효율: {(len(test_data)/perf_results['duration'])/(len(test_data)/concurrency):.2f}x")
    
    return {
        "type": "concurrent",
        "concurrency": concurrency,
        "total_time": perf_results['duration'],
        "throughput": len(test_data)/perf_results['duration'],
        "success_rate": total_success/len(test_data)
    }


def test_memory_usage():
    """메모리 사용량 테스트"""
    
    print("\n💾 메모리 사용량 테스트")
    print("=" * 50)
    
    process = psutil.Process(os.getpid())
    
    # 기본 메모리 사용량
    base_memory = process.memory_info().rss / 1024 / 1024
    
    # 대량 데이터 생성
    large_data = generate_test_data(1000)
    after_generation = process.memory_info().rss / 1024 / 1024
    
    # 데이터 처리 시뮬레이션
    processed_data = []
    for data in large_data:
        processed_data.append({
            **data,
            "processed": True,
            "timestamp": time.time()
        })
    
    after_processing = process.memory_info().rss / 1024 / 1024
    
    # 정리
    del large_data
    del processed_data
    
    after_cleanup = process.memory_info().rss / 1024 / 1024
    
    print(f"📊 메모리 사용량 분석:")
    print(f"   기본 메모리: {base_memory:.1f}MB")
    print(f"   데이터 생성 후: {after_generation:.1f}MB (+{after_generation-base_memory:.1f}MB)")
    print(f"   처리 후: {after_processing:.1f}MB (+{after_processing-base_memory:.1f}MB)")
    print(f"   정리 후: {after_cleanup:.1f}MB (+{after_cleanup-base_memory:.1f}MB)")


async def main():
    """메인 성능 테스트 함수"""
    
    print("🎯 북마크 저장 시스템 성능 테스트 시작!")
    print("=" * 60)
    
    # 테스트 설정
    test_sizes = [10, 50, 100]
    all_results = []
    
    for size in test_sizes:
        print(f"\n🔢 테스트 크기: {size}개 메시지")
        print("=" * 40)
        
        test_data = generate_test_data(size)
        
        # 1. Consumer 성능 테스트
        consumer_result = await test_consumer_performance(test_data)
        all_results.append(consumer_result)
        
        # 2. RabbitMQ 성능 테스트 (연결 가능한 경우)
        try:
            rabbitmq_result = await test_rabbitmq_performance(test_data)
            if rabbitmq_result:
                all_results.append(rabbitmq_result)
        except Exception as e:
            print(f"⚠️ RabbitMQ 테스트 건너뜀: {e}")
        
        # 3. 동시 처리 테스트 (큰 데이터셋에서만)
        if size >= 50:
            concurrent_result = await test_concurrent_processing(test_data, concurrency=3)
            all_results.append(concurrent_result)
    
    # 4. 메모리 사용량 테스트
    test_memory_usage()
    
    # 전체 결과 요약
    print("\n" + "=" * 60)
    print("📊 전체 성능 테스트 결과 요약")
    print("=" * 60)
    
    for result in all_results:
        if result:
            print(f"\n📈 {result['type'].upper()} 테스트:")
            print(f"   처리량: {result['throughput']:.2f} 메시지/초")
            print(f"   성공률: {result['success_rate']*100:.1f}%")
            if 'avg_processing_time' in result:
                print(f"   평균 처리 시간: {result['avg_processing_time']*1000:.2f}ms")
    
    print("\n🎉 성능 테스트 완료!")


if __name__ == "__main__":
    # 환경 변수 로드
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️ python-dotenv가 없습니다. 환경변수를 수동으로 설정해주세요.")
    
    asyncio.run(main()) 