"""
S3에서 HTML 파일을 다운로드하는 서비스

이 모듈은 AWS S3에서 HTML 파일을 다운로드하고, 해당 파일의 내용을 문자열로 반환하는 기능을 제공합니다.
"""
import os

import boto3
from app.core.config import settings

def download_html_from_s3(s3_key: str) -> str:
    """
    S3에서 HTML 파일을 다운로드하여 HTML 문자열을 반환
    
    Args:
        s3_key (str): S3에 저장된 HTML 파일의 키
    Returns:
        str: 다운로드된 HTML 파일의 내용
    """
    session = boto3.session.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_KEY_ID,
        region_name=settings.REGION
    )
    bucket_name = settings.BUCKET_NAME

    s3 = session.client('s3')
    local_file_path = os.path.join("/tmp", os.path.basename(s3_key))

    s3.download_file(bucket_name, s3_key, local_file_path)

    with open(local_file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()

    os.remove(local_file_path)

    return html_content
