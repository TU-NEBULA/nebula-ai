from fastapi import APIRouter
from app.models.keyword_extractor import UrlInput
from app.services.keyword_extractor import extract_keywords_from_url

router = APIRouter()

@router.post("/extract_keywords")
async def extract_keywords(url_input: UrlInput):
    keywords = extract_keywords_from_url(url_input.url)
    return {
        "url": url_input.url,
        "keywords": keywords
    }