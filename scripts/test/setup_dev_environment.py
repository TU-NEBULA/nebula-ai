#!/usr/bin/env python3
"""
개발 환경 설정 가이드 스크립트

북마크 저장 시스템을 실제로 테스트하기 위한 
개발 환경 설정을 도와주는 스크립트입니다.
"""

import os
import sys
import subprocess
from pathlib import Path
import shutil


def print_step(step_num: int, title: str):
    """단계별 제목 출력"""
    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {title}")
    print(f"{'='*60}")


def check_command_exists(command: str) -> bool:
    """명령어가 시스템에 있는지 확인"""
    return shutil.which(command) is not None


def run_command(command: str, check: bool = True) -> bool:
    """명령어 실행"""
    try:
        print(f"🔄 실행 중: {command}")
        result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
        if result.stdout:
            print(f"✅ 출력: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 오류: {e}")
        if e.stderr:
            print(f"오류 내용: {e.stderr.strip()}")
        return False


def check_prerequisites():
    """필수 도구들 확인"""
    print_step(1, "필수 도구 확인")
    
    required_tools = {
        'docker': 'Docker Desktop',
        'docker-compose': 'Docker Compose',
        'python3': 'Python 3.8+',
        'pipenv': 'Pipenv (pip install pipenv)'
    }
    
    missing_tools = []
    
    for tool, description in required_tools.items():
        if check_command_exists(tool):
            print(f"✅ {tool} 설치됨")
        else:
            print(f"❌ {tool} 없음 - {description} 설치 필요")
            missing_tools.append(tool)
    
    if missing_tools:
        print(f"\n⚠️ 다음 도구들을 먼저 설치해주세요: {', '.join(missing_tools)}")
        return False
    
    print("\n🎉 모든 필수 도구가 설치되어 있습니다!")
    return True


def setup_environment_file():
    """환경 설정 파일 생성"""
    print_step(2, "환경 설정 파일 생성")
    
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    env_example = project_root / "env.example"
    
    if env_file.exists():
        print("✅ .env 파일이 이미 존재합니다.")
        overwrite = input("덮어쓰시겠습니까? (y/N): ").strip().lower()
        if overwrite != 'y':
            return True
    
    if not env_example.exists():
        print("❌ env.example 파일을 찾을 수 없습니다.")
        return False
    
    # env.example을 .env로 복사
    shutil.copy2(env_example, env_file)
    
    print("📝 기본 개발 환경 설정...")
    
    # 개발용 설정으로 일부 값 변경
    dev_settings = {
        'ENVIRONMENT': 'development',
        'DEBUG': 'true',
        'POSTGRES_HOST': 'localhost',
        'POSTGRES_PORT': '5432',
        'POSTGRES_USER': 'nebula_user',
        'POSTGRES_PASSWORD': 'nebula_password',
        'POSTGRES_DB': 'nebula_ai_dev',
        'RABBITMQ_HOST': 'localhost',
        'REDIS_HOST': 'localhost',
        'CHROMA_DB_URI': './chroma_db'
    }
    
    # .env 파일 내용 읽기
    with open(env_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 개발용 설정으로 변경
    for key, value in dev_settings.items():
        # 기존 설정 라인 찾아서 교체
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith(f'{key}='):
                lines[i] = f'{key}={value}'
                break
        content = '\n'.join(lines)
    
    # 수정된 내용 저장
    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 환경 설정 파일 생성됨: {env_file}")
    print("⚠️ 필요에 따라 .env 파일의 API 키들을 설정해주세요.")
    
    return True


def setup_infrastructure():
    """인프라 서비스 설정 (Docker)"""
    print_step(3, "인프라 서비스 설정")
    
    print("🐳 Docker 서비스 시작...")
    
    services = [
        "docker-compose up -d rabbitmq",
        "docker-compose up -d redis", 
        "docker-compose up -d postgres"  # PostgreSQL이 있다면
    ]
    
    for service_cmd in services:
        success = run_command(service_cmd, check=False)
        if not success:
            print(f"⚠️ {service_cmd} 실행 실패 - 수동으로 확인해주세요.")
    
    print("\n⏳ 서비스 준비 시간 대기 중...")
    import time
    time.sleep(10)
    
    # 서비스 상태 확인
    run_command("docker-compose ps", check=False)
    
    return True


def install_dependencies():
    """Python 의존성 설치"""
    print_step(4, "Python 의존성 설치")
    
    commands = [
        "pipenv install --dev",
        "pipenv run pip install python-dotenv"  # 환경변수 로드용
    ]
    
    for cmd in commands:
        success = run_command(cmd)
        if not success:
            print(f"⚠️ {cmd} 실행 실패")
            return False
    
    print("✅ 의존성 설치 완료!")
    return True


def setup_database():
    """데이터베이스 초기화"""
    print_step(5, "데이터베이스 초기화")
    
    print("🗄️ 데이터베이스 초기화...")
    
    # 데이터베이스 초기화 스크립트 실행
    success = run_command("pipenv run python scripts/init_database.py", check=False)
    
    if success:
        print("✅ 데이터베이스 초기화 완료!")
    else:
        print("⚠️ 데이터베이스 초기화 실패 - 수동으로 확인해주세요.")
    
    return True


def start_services():
    """필요한 서비스들 시작"""
    print_step(6, "서비스 시작")
    
    print("📋 다음 명령어들을 각각 별도 터미널에서 실행하세요:")
    print()
    print("1️⃣ Consumer 시작:")
    print("   pipenv run python -m app.consumers.bookmark_save_rmq")
    print()
    print("2️⃣ Celery Worker 시작:")
    print("   pipenv run celery -A app.core.celery_worker worker --loglevel=info -Q embedding")
    print()
    print("3️⃣ FastAPI 서버 시작 (선택적):")
    print("   pipenv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload")
    print()
    print("4️⃣ Flower 모니터링 (선택적):")
    print("   pipenv run celery -A app.core.celery_worker flower")
    
    return True


def run_test():
    """테스트 실행"""
    print_step(7, "테스트 실행")
    
    print("🧪 테스트 스크립트 실행...")
    
    # 수동 테스트 스크립트 실행
    test_script = Path(__file__).parent / "manual_bookmark_test.py"
    
    if test_script.exists():
        print(f"📝 테스트 스크립트: {test_script}")
        print("다음 명령어로 테스트를 실행할 수 있습니다:")
        print(f"   pipenv run python {test_script}")
    else:
        print("❌ 테스트 스크립트를 찾을 수 없습니다.")
    
    return True


def main():
    """메인 설정 함수"""
    
    print("🚀 북마크 저장 시스템 개발 환경 설정")
    print("=" * 60)
    
    steps = [
        ("필수 도구 확인", check_prerequisites),
        ("환경 설정", setup_environment_file),
        ("인프라 설정", setup_infrastructure),
        ("의존성 설치", install_dependencies),
        ("데이터베이스 초기화", setup_database),
        ("서비스 시작 가이드", start_services),
        ("테스트 방법", run_test)
    ]
    
    for i, (name, func) in enumerate(steps, 1):
        try:
            success = func()
            if not success:
                print(f"\n❌ {name} 단계에서 문제가 발생했습니다.")
                choice = input("계속하시겠습니까? (y/N): ").strip().lower()
                if choice != 'y':
                    break
        except KeyboardInterrupt:
            print("\n\n⏹️ 사용자에 의해 중단되었습니다.")
            break
        except Exception as e:
            print(f"\n❌ {name} 단계에서 오류 발생: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 개발 환경 설정 가이드 완료!")
    print("=" * 60)
    
    print("\n📚 다음 단계:")
    print("1. 각 터미널에서 서비스들을 시작하세요")
    print("2. manual_bookmark_test.py를 실행하여 테스트하세요")
    print("3. 문제가 있으면 로그를 확인하세요")


if __name__ == "__main__":
    main() 