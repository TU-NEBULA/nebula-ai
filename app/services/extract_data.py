from __future__ import annotations

import asyncio
from functools import partial

from bs4 import BeautifulSoup
from app.external.s3_service import download_html_from_s3
from app.utils.text_processing import extract_main_text, extract_keywords_tfidf
from app.core.config import settings

BASE_THUMBNAIL = settings.BASE_THUMBNAIL

def extract_data_from_s3(user_id: int, s3_key: str):
    """s3 키를 입력받아 HTML에서 데이터 추출"""
    html_content = download_html_from_s3(s3_key)

    soup = BeautifulSoup(html_content, 'html.parser')
    og_image = soup.find('meta', property='og:image')

    if og_image and og_image.get('content'):
        thumbnail = og_image['content']
    else:
        thumbnail = BASE_THUMBNAIL

    main_text = extract_main_text(html_content)
    keywords = extract_keywords_tfidf(user_id, main_text, s3_key)

    return {
        "image_url": thumbnail,
        "keywords": keywords
    }


async def extract_data_from_s3_async(user_id: int, s3_key: str):
    """
    ThreadPoolExecutor로 extract_data_from_s3 off-load 하여
    이벤트 루프를 블로킹하지 않고 재사용.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, partial(extract_data_from_s3, user_id, s3_key)
    )
