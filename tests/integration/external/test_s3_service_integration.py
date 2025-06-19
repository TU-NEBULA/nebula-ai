import os
import boto3
import pytest
from botocore.exceptions import ClientError

from app.core.config import settings
from app.external.s3_service import download_html_from_s3

TEST_S3_KEY = getattr(settings, "TEST_S3_KEY", "html_files/(번역) 리액트 개발자를 위한 SSR 심층 분석/084f2539-b658-49c5-8b3d-ba302093bcaa_content.html")


@pytest.mark.integration
def test_head_bucket_access():
    """
    HEAD_BUCKET 호출로 버킷 존재 여부 및 접근 권한 확인.
    """
    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_KEY_ID,
        region_name=settings.REGION,
    )
    try:
        resp = client.head_bucket(Bucket=settings.BUCKET_NAME)
    except ClientError as e:
        pytest.skip(f"S3 접근 불가: {e}")
    # HTTPStatusCode 가 200 이면 성공
    status = resp["ResponseMetadata"]["HTTPStatusCode"]
    assert status == 200, f"버킷 접근 실패: HTTP {status}"

@pytest.mark.integration
def test_download_html_from_s3_real():
    """
    download_html_from_s3 함수로 실제 객체를 가져와 HTML 컨텐츠를 읽고
    임시 파일이 잘 삭제되는지 확인.
    """
    # 만약 TEST_S3_KEY 가 설정되지 않았다면 테스트 스킵
    if not TEST_S3_KEY:
        pytest.skip("환경 변수 TEST_S3_KEY 가 설정되어 있지 않습니다.")

    # 실제 다운로드
    html = download_html_from_s3(TEST_S3_KEY)
    assert html, "다운로드한 HTML이 비어있습니다."
    assert "<html" in html.lower(), "다운로드한 내용이 HTML 같지 않습니다."

    # 로컬 임시 파일 경로 확인
    tmp_path = os.path.join("/tmp", os.path.basename(TEST_S3_KEY))
    assert not os.path.exists(tmp_path), "임시 파일이 삭제되지 않았습니다."

def test_list_objects_and_debug():
    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_KEY_ID,
        region_name=settings.REGION,
    )

    # TEST_S3_KEY의 폴더(prefix)만 잘라서 리스트 조회
    if not TEST_S3_KEY or "/" not in TEST_S3_KEY:
        pytest.skip("TEST_S3_KEY가 비어있거나 prefix를 추출할 수 없습니다.")

    # prefix = TEST_S3_KEY.rsplit("/", 1)[0] + "/"
    # resp = client.list_objects_v2(
    #     Bucket=settings.BUCKET_NAME,
    #     Prefix=prefix,
    #     MaxKeys=50,
    # )

    resp = client.list_objects_v2(
        Bucket=settings.BUCKET_NAME,
        MaxKeys=50,
    )

    print("\n--- S3 버킷 정보 ---")
    print(settings.BUCKET_NAME)
    print(settings.AWS_ACCESS_KEY_ID)
    print(settings.AWS_SECRET_KEY_ID)
    print(settings.REGION)

    keys = [obj["Key"] for obj in resp.get("Contents", [])]
    print("\n--- S3 버킷에 존재하는 Key 목록 (최대 50개) ---")
    for k in keys:
        print(k)
    print("--- END ---\n")

    assert TEST_S3_KEY in keys, (
        f"❌ TEST_S3_KEY (`{TEST_S3_KEY}`) 가 S3 버킷에 없습니다.\n"
        f"위 목록에서 정확한 Key를 골라 `.env` 에 다시 설정하세요."
    )
