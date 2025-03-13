import pytest
from unittest.mock import patch
from app.routers.extract_data import extract_data
from app.schemas.extract_data_request import ExtractDataRequest
from app.schemas.extract_data_response import ExtractDataResponse

@pytest.fixture
def mock_request_data():
    return {
        "id": "test_neo4j_id",
        "user_id": "test_user_id",
        "s3_key": "html_files/expo 소셜 로그인/b2cdc2c2-d935-492a-bba6-26f6bfde4de4_test.html"
    }

@pytest.fixture
def mock_response_data():
    return {
        "id": "test_neo4j_id",
        "image_url": "https://s3.amazonaws.com/test_bucket/test_image.jpg",
        "keywords": ["인공지능", "자연어 처리", "딥러닝"]
    }

@patch("app.routers.extract_data.extract_data_from_s3")
def test_extract_data_api(mock_extract_data, test_client, mock_request_data, mock_response_data):
    """
    /extract_data API 테스트
    """
    mock_extract_data.return_value = mock_response_data

    response = test_client.post("/api/extract_data", json=mock_request_data)
    
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == mock_response_data["id"]
    assert data["image_url"] == mock_response_data["image_url"]
    assert data["keywords"] == mock_response_data["keywords"]
