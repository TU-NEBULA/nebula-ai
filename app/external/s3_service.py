import boto3
import os
from app.core.config import settings 

def download_html_from_s3(s3_key):
    """S3에서 HTML 파일을 다운로드하여 HTML 문자열을 반환"""
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
