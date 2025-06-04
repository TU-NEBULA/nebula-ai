"""
S3에서 HTML 파일을 다운로드하는 서비스

이 모듈은 AWS S3에서 HTML 파일을 다운로드하고, 해당 파일의 내용을 문자열로 반환하는 기능을 제공합니다.
"""
import os
import requests

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from loguru import logger
from app.core.config import settings

def download_html_from_url(url: str) -> str:
    """
    URL에서 직접 HTML을 다운로드하여 HTML 문자열을 반환
    
    Args:
        url (str): HTML을 가져올 URL
    Returns:
        str: 다운로드된 HTML 파일의 내용
    Raises:
        ConnectionError: URL 연결에 실패한 경우
        ValueError: 잘못된 URL이나 응답인 경우
    """
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        
        logger.info(f"🌐 URL에서 HTML 다운로드 시작: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 인코딩 처리
        if response.encoding:
            html_content = response.text
        else:
            # 인코딩이 감지되지 않는 경우 UTF-8로 시도
            html_content = response.content.decode('utf-8', errors='ignore')
        
        logger.info(f"✅ URL에서 HTML 다운로드 완료: {url} (길이: {len(html_content)})")
        return html_content
        
    except requests.exceptions.Timeout as e:
        logger.error(f"❌ URL 다운로드 타임아웃: {url}")
        raise ConnectionError(f"URL 다운로드 타임아웃: {url}") from e
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ URL 연결 실패: {url}")
        raise ConnectionError(f"URL 연결 실패: {url}") from e
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ HTTP 오류: {url}, 상태코드: {response.status_code}")
        raise ConnectionError(f"HTTP 오류: {url}, 상태코드: {response.status_code}") from e
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ URL 요청 실패: {url}, 오류: {e}")
        raise ConnectionError(f"URL 요청 실패: {url}") from e
    except UnicodeDecodeError as e:
        logger.error(f"❌ HTML 디코딩 실패: {url}")
        raise ValueError(f"HTML 디코딩 실패: {url}") from e
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {url}, 오류: {e}")
        raise ConnectionError(f"URL 다운로드 중 오류: {url}") from e


def download_html_from_s3(s3_key: str) -> str:
    """
    S3에서 HTML 파일을 다운로드하여 HTML 문자열을 반환
    
    Args:
        s3_key (str): S3에 저장된 HTML 파일의 키
    Returns:
        str: 다운로드된 HTML 파일의 내용
    Raises:
        FileNotFoundError: S3에서 파일을 찾을 수 없는 경우
        ConnectionError: S3 연결에 실패한 경우
        ValueError: 잘못된 설정이나 매개변수인 경우
    """
    try:
        session = boto3.session.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_KEY_ID,
            region_name=settings.REGION
        )
        bucket_name = settings.BUCKET_NAME

        s3 = session.client('s3')
        
        # 파일 존재 여부 확인
        try:
            s3.head_object(Bucket=bucket_name, Key=s3_key)
            logger.info(f"✅ S3 파일 존재 확인 완료: {s3_key}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.error(f"❌ S3 파일이 존재하지 않음: {s3_key}")
                raise FileNotFoundError(f"S3에서 파일을 찾을 수 없습니다: {s3_key}") from e
            else:
                logger.error(f"❌ S3 파일 확인 중 오류 발생: {error_code}")
                raise ConnectionError(f"S3 파일 확인 실패: {error_code}") from e

        local_file_path = os.path.join("/tmp", os.path.basename(s3_key))

        # 파일 다운로드
        s3.download_file(bucket_name, s3_key, local_file_path)
        logger.info(f"✅ S3 파일 다운로드 완료: {s3_key}")

        # 파일 읽기
        with open(local_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()

        # 임시 파일 정리
        os.remove(local_file_path)

        return html_content

    except NoCredentialsError as e:
        logger.error("❌ AWS 자격 증명이 설정되지 않았습니다")
        raise ValueError("AWS 자격 증명이 필요합니다") from e
    except ClientError as e:
        # head_object에서 이미 처리된 경우가 아니라면 다른 ClientError
        if 'already handled' not in str(e):
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"❌ S3 클라이언트 오류: {error_code}")
            raise ConnectionError(f"S3 작업 실패: {error_code}") from e
        raise
    except OSError as e:
        logger.error(f"❌ 파일 시스템 오류: {e}")
        raise ConnectionError(f"파일 처리 실패: {e}") from e
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
        raise ConnectionError(f"S3 다운로드 중 오류: {e}") from e
