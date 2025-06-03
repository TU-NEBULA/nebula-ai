#!/usr/bin/env python3
"""
테스트 데이터 헬퍼 유틸리티

테스트에서 사용할 HTML 파일과 샘플 데이터를 쉽게 가져올 수 있는 함수들을 제공합니다.
"""

import os
import random
from pathlib import Path
from typing import Dict, List, Optional


class TestDataHelper:
    """테스트 데이터 관리 헬퍼 클래스"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.data_dir = self.project_root / "tests" / "data"
        self.html_dir = self.data_dir / "html"
    
    def get_html_files(self) -> List[str]:
        """사용 가능한 HTML 파일 목록 반환"""
        if not self.html_dir.exists():
            return []
        
        return [f.name for f in self.html_dir.glob("*.html")]
    
    def get_html_content(self, filename: str) -> Optional[str]:
        """HTML 파일 내용을 읽어서 반환"""
        file_path = self.html_dir / filename
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"파일 읽기 오류: {e}")
            return None
    
    def get_sample_bookmark_data(self, html_filename: Optional[str] = None) -> Dict:
        """샘플 북마크 데이터 생성"""
        
        # HTML 파일 선택
        if html_filename is None:
            available_files = self.get_html_files()
            if available_files:
                html_filename = random.choice(available_files)
            else:
                html_filename = "default.html"
        
        # 파일명에 따른 데이터 매핑
        data_mapping = {
            "ai_machine_learning.html": {
                "title": "AI와 머신러닝 기초",
                "url": "https://example.com/ai-ml-guide",
                "keywords": ["AI", "머신러닝", "딥러닝", "인공지능", "기술"],
                "memo": "AI와 머신러닝의 기본 개념을 다룬 유용한 자료",
                "summary": "인공지능과 머신러닝의 기초 개념, 주요 기술들에 대한 종합적인 가이드"
            },
            "web_development.html": {
                "title": "웹 개발 완벽 가이드",
                "url": "https://example.com/web-dev-guide",
                "keywords": ["웹개발", "프론트엔드", "백엔드", "JavaScript", "React"],
                "memo": "모던 웹 개발의 핵심 기술들을 정리한 문서",
                "summary": "프론트엔드와 백엔드 기술, DevOps까지 포함한 웹 개발 전반에 대한 가이드"
            },
            "data_science.html": {
                "title": "데이터 사이언스로의 여행",
                "url": "https://example.com/data-science-journey",
                "keywords": ["데이터사이언스", "빅데이터", "분석", "파이썬", "머신러닝"],
                "memo": "데이터 사이언스 입문을 위한 종합 가이드",
                "summary": "데이터 사이언스의 기본 개념부터 실무 도구, 프로세스까지 다룬 완전한 가이드"
            },
            "blockchain_crypto.html": {
                "title": "블록체인 혁명의 시대",
                "url": "https://example.com/blockchain-revolution",
                "keywords": ["블록체인", "암호화폐", "비트코인", "이더리움", "DeFi"],
                "memo": "블록체인 기술과 암호화폐 생태계에 대한 포괄적 분석",
                "summary": "블록체인 기술의 핵심 개념, 주요 암호화폐, 실제 응용 분야와 위험 요소까지 다룬 완전한 가이드"
            }
        }
        
        # 기본 데이터
        base_data = {
            "title": "테스트 북마크",
            "url": "https://example.com/test",
            "keywords": ["테스트", "북마크", "샘플"],
            "memo": "테스트용 북마크 메모",
            "summary": "테스트를 위한 샘플 북마크입니다."
        }
        
        # 파일별 특화 데이터 가져오기
        specific_data = data_mapping.get(html_filename, {})
        base_data.update(specific_data)
        
        return base_data
    
    def create_test_message(self, 
                          user_id: int = None, 
                          star_id: str = None, 
                          html_filename: str = None) -> Dict:
        """완전한 테스트 메시지 데이터 생성"""
        
        if user_id is None:
            user_id = random.randint(100, 999)
        
        if star_id is None:
            star_id = f"test_{user_id}_{random.randint(1000, 9999)}"
        
        if html_filename is None:
            available_files = self.get_html_files()
            if available_files:
                html_filename = random.choice(available_files)
            else:
                html_filename = "test.html"
        
        # 기본 데이터 가져오기
        bookmark_data = self.get_sample_bookmark_data(html_filename)
        
        # 메시지 형식으로 변환
        message_data = {
            "userId": user_id,
            "starId": star_id,
            "s3Key": f"tests/data/html/{html_filename}",
            "title": bookmark_data["title"],
            "url": bookmark_data["url"],
            "keywords": bookmark_data["keywords"],
            "memo": bookmark_data["memo"],
            "summary": bookmark_data["summary"]
        }
        
        return message_data
    
    def get_test_scenarios(self) -> List[Dict]:
        """다양한 테스트 시나리오 데이터 생성"""
        
        scenarios = []
        html_files = self.get_html_files()
        
        if not html_files:
            # HTML 파일이 없는 경우 기본 시나리오
            scenarios.append({
                "name": "기본 테스트",
                "data": self.create_test_message()
            })
            return scenarios
        
        # 각 HTML 파일에 대한 시나리오 생성
        for i, html_file in enumerate(html_files):
            scenario_name = html_file.replace('.html', '').replace('_', ' ').title()
            
            scenarios.append({
                "name": f"{scenario_name} 테스트",
                "data": self.create_test_message(
                    user_id=200 + i,
                    html_filename=html_file
                ),
                "html_file": html_file,
                "should_succeed": True
            })
        
        # 오류 시나리오 추가
        scenarios.extend([
            {
                "name": "필수 필드 누락 테스트",
                "data": {
                    "userId": 999,
                    "starId": "error_test_001",
                    "s3Key": "tests/data/html/ai_machine_learning.html",
                    # title 누락
                    "url": "https://example.com/error",
                    "keywords": ["오류", "테스트"],
                    "memo": "필수 필드 누락 테스트",
                    "summary": "title 필드가 누락된 테스트"
                },
                "should_succeed": False
            },
            {
                "name": "잘못된 사용자 ID 테스트",
                "data": {
                    "userId": "invalid_user_id",  # 문자열 타입
                    "starId": "error_test_002", 
                    "s3Key": "tests/data/html/web_development.html",
                    "title": "잘못된 사용자 ID 테스트",
                    "url": "https://example.com/invalid-user",
                    "keywords": ["오류", "테스트"],
                    "memo": "잘못된 타입 테스트",
                    "summary": "userId가 잘못된 타입인 테스트"
                },
                "should_succeed": False
            }
        ])
        
        return scenarios
    
    def get_performance_test_data(self, count: int) -> List[Dict]:
        """성능 테스트용 대량 데이터 생성"""
        
        test_data = []
        html_files = self.get_html_files()
        
        if not html_files:
            html_files = ["default.html"]
        
        for i in range(count):
            html_file = html_files[i % len(html_files)]
            
            data = self.create_test_message(
                user_id=1000 + (i % 100),  # 100명의 사용자로 분산
                star_id=f"perf_test_{i:06d}",
                html_filename=html_file
            )
            
            # 성능 테스트용 데이터 변형
            data["title"] = f"성능 테스트 북마크 #{i:06d} - " + data["title"]
            data["memo"] = f"성능 테스트용 메모 #{i:06d} - " + data["memo"]
            data["summary"] = f"성능 테스트 #{i:06d}의 요약. " + data["summary"]
            
            test_data.append(data)
        
        return test_data


# 전역 헬퍼 인스턴스
test_data_helper = TestDataHelper()


def get_sample_data(html_filename: str = None) -> Dict:
    """간편한 샘플 데이터 생성 함수"""
    return test_data_helper.create_test_message(html_filename=html_filename)


def get_test_scenarios() -> List[Dict]:
    """간편한 테스트 시나리오 생성 함수"""
    return test_data_helper.get_test_scenarios()


def get_html_content(filename: str) -> Optional[str]:
    """간편한 HTML 콘텐츠 읽기 함수"""
    return test_data_helper.get_html_content(filename)


if __name__ == "__main__":
    # 테스트 데이터 헬퍼 확인
    print("🔧 테스트 데이터 헬퍼 정보")
    print("=" * 40)
    
    helper = TestDataHelper()
    
    print(f"HTML 파일 위치: {helper.html_dir}")
    print(f"사용 가능한 HTML 파일: {helper.get_html_files()}")
    
    print("\n📄 샘플 데이터 예시:")
    sample = helper.create_test_message()
    for key, value in sample.items():
        print(f"  {key}: {value}")
    
    print(f"\n🎯 테스트 시나리오 수: {len(helper.get_test_scenarios())}")
    
    print("\n✅ 테스트 데이터 헬퍼가 정상적으로 작동합니다!") 