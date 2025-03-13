import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def test_client():
    """FastAPI 테스트 클라이언트 생성"""
    with TestClient(app) as client:
        yield client
