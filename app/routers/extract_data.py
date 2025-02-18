from fastapi import APIRouter
from app.services.extract_data import extract_data_from_s3
from app.schemas.extract_data_request import ExtractDataRequest
from app.schemas.extract_data_response import ExtractDataResponse

router = APIRouter()

@router.post("/extract_data", response_model=ExtractDataResponse)
def extract_data(request: ExtractDataRequest):
    """Neo4j id와 S3 키를 입력받아 S3에 있는 HTML 문자열 임베딩 변환"""    
    data = extract_data_from_s3(request.id, request.s3_key)

    return ExtractDataResponse(
        id=request.id,
        image_url=data["image_url"],
        keywords=data["keywords"]
    )
