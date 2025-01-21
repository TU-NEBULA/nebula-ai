from fastapi import APIRouter, HTTPException
from app.models.extract_data import DataInputs
from app.services.extract_data import extract_data_from_html
from app.common.response.base_response import success_response, error_response

import requests

router = APIRouter()

@router.post("/extract_data")
async def extract_data(data_input: DataInputs):
    try:
        url = data_input.url
        html_content = data_input.html_content

        print(f"URL: {url}")
        print(f"HTML Content: {html_content}")

        if html_content == "":
            response = requests.get(url)    
            response.raise_for_status()
            html_content = response.text

        data = extract_data_from_html(html_content)

        from pprint import pprint
        pprint(data)

        return_data = {
            "thumbnail": data.get("thumbnail", ""),
            "url": data_input.url,
            "keywords": data.get("keywords", [])
        }

        return success_response(data=return_data)
        
    except requests.RequestException as e:
        return error_response(code=500, message=f"An error occurred: {str(e)}")