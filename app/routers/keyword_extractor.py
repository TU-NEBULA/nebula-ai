from fastapi import APIRouter, HTTPException
from app.models.keyword_extractor import DataInputs
from app.services.keyword_extractor import extract_data_from_html

import requests

router = APIRouter()

@router.post("/extract_data")
async def extract_data(data_input: DataInputs):
    try:
        url = data_input.url
        html_content = data_input.html_content

        if html_content == "":
            response = requests.get(url)    
            response.raise_for_status()
            html_content = response.text

        data = extract_data_from_html(html_content)

        return {
            "thubmnail": data.get("thumbnail", ""),
            "url": data_input.url,
            "keywords": data.get("keywords", [])
        }
    
    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {str(e)}")