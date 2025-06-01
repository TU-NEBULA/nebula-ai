"""
웹 콘텐츠 데이터 추출 모듈

이 모듈은 S3에 저장된 HTML 콘텐츠에서 유용한 데이터를 추출하는 기능을 제공합니다.
썸네일 이미지와 키워드를 추출하며, 동기 및 비동기 방식으로 사용할 수 있습니다.
"""
from __future__ import annotations

import asyncio
from functools import partial

from bs4 import BeautifulSoup
from app.external.s3_service import download_html_from_s3
from app.utils.text_processing import extract_main_text, extract_keywords
from app.core.config import settings

# 썸네일 이미지가 없을 때 사용할 기본 이미지 URL
BASE_THUMBNAIL = settings.BASE_THUMBNAIL

def extract_data_from_s3(user_id: int, s3_key: str) -> dict:
    """
    S3에 저장된 HTML 콘텐츠에서 썸네일 이미지와 키워드를 추출합니다.
    
    HTML 콘텐츠에서 다음 작업을 수행합니다:
    1. S3에서 HTML 콘텐츠를 다운로드합니다.
    2. og:image 메타 태그에서 썸네일 이미지를 추출합니다.
    3. 텍스트 처리 기능을 사용하여 키워드를 추출합니다.
    
    Args:
        user_id (int): 사용자 ID
        s3_key (str): S3에 저장된 HTML 콘텐츠의 키
        
    Returns:
        dict: 썸네일 이미지 URL과 추출된 키워드를 포함한 딕셔너리
    """
    # S3에서 HTML 콘텐츠 다운로드
    html_content = download_html_from_s3(s3_key)

    # BeautifulSoup으로 HTML 파싱
    soup = BeautifulSoup(html_content, 'html.parser')
    # Open Graph 이미지 메타 태그 찾기
    og_image = soup.find('meta', property='og:image')

    # 썸네일 이미지 URL 설정 (없으면 기본 이미지 사용)
    if og_image and og_image.get('content'):
        thumbnail = og_image['content']
    else:
        thumbnail = BASE_THUMBNAIL

    # HTML에서 본문 텍스트 추출
    main_text = extract_main_text(html_content)
    # 새로운 키워드 추출 함수 사용
    keywords = extract_keywords(main_text, max_keywords=10)

    # 결과 반환
    return {
        "image_url": thumbnail,  # 썸네일 이미지 URL
        "keywords": keywords     # 추출된 키워드 목록
    }


async def extract_data_from_s3_async(user_id: int, s3_key: str) -> dict:
    """
    S3에서 비동기적으로 데이터를 추출하는 함수입니다.
    
    ThreadPoolExecutor를 사용하여 extract_data_from_s3 함수를 오프로드하여
    이벤트 루프를 블로킹하지 않고 재사용할 수 있도록 합니다.
    
    Args:
        user_id (int): 사용자 ID
        s3_key (str): S3에 저장된 HTML 콘텐츠의 키
        
    Returns:
        dict: 썸네일 이미지 URL과 추출된 키워드를 포함한 딕셔너리
    """
    # 현재 실행 중인 이벤트 루프 가져오기
    loop = asyncio.get_running_loop()
    # ThreadPoolExecutor를 사용하여 동기 함수를 비동기적으로 실행
    return await loop.run_in_executor(
        None, partial(extract_data_from_s3, user_id, s3_key)
    )
