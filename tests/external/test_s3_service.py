# tests/test_s3_utils.py

import os
import builtins
import pytest
import boto3
from unittest import mock

from app.external.s3_service import download_html_from_s3
from app.core.config import settings

# 1) boto3.session.Session 모킹
class DummyS3Client:
    def download_file(self, bucket, key, path):
        # /tmp/<basename(key)> 에 HTML 파일을 쓴다고 가정
        with open(path, 'w', encoding='utf-8') as f:
            f.write('<html><body>테스트 콘텐츠</body></html>')

class DummySession:
    def __init__(self, *args, **kwargs):
        pass

    def client(self, service_name):
        assert service_name == 's3'
        return DummyS3Client()

def test_download_html_success(monkeypatch):
    # 1. settings에 아무 값이나 세팅 (함수 로직상 실제 사용하지 않음)
    monkeypatch.setattr(settings, 'AWS_ACCESS_KEY_ID', 'dummy_id')
    monkeypatch.setattr(settings, 'AWS_SECRET_KEY_ID', 'dummy_secret')
    monkeypatch.setattr(settings, 'REGION', 'ap-northeast-2')
    monkeypatch.setattr(settings, 'BUCKET_NAME', 'dummy-bucket')

    # 2. boto3.session.Session 을 DummySession 으로 교체
    monkeypatch.setattr(boto3.session, 'Session', DummySession)

    s3_key = 'path/to/test.html'
    html = download_html_from_s3(s3_key)

    # 3. 반환값 검증
    assert '<body>테스트 콘텐츠</body>' in html

    # 4. 다운로드된 파일이 삭제되었는지 확인
    tmp_path = os.path.join('/tmp', os.path.basename(s3_key))
    assert not os.path.exists(tmp_path)

def test_download_html_download_error(monkeypatch):
    # download_file 호출 시 예외가 발생하면 그대로 전파되는지 확인

    class ErrorClient:
        def download_file(self, bucket, key, path):
            raise RuntimeError("S3 다운로드 실패")

    class ErrorSession:
        def __init__(self, *args, **kwargs):
            pass
        def client(self, service_name):
            return ErrorClient()

    # settings 모킹
    monkeypatch.setattr(settings, 'AWS_ACCESS_KEY_ID', 'x')
    monkeypatch.setattr(settings, 'AWS_SECRET_KEY_ID', 'y')
    monkeypatch.setattr(settings, 'REGION', 'ap-northeast-2')
    monkeypatch.setattr(settings, 'BUCKET_NAME', 'bucket')

    # Session 모킹
    monkeypatch.setattr(boto3.session, 'Session', ErrorSession)

    with pytest.raises(RuntimeError) as excinfo:
        download_html_from_s3('anykey.html')
    assert "S3 다운로드 실패" in str(excinfo.value)
