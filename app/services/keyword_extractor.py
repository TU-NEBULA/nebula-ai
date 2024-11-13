import requests
from bs4 import BeautifulSoup
from fastapi import HTTPException

def extract_keywords_from_url(url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()
        
        return text

    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {str(e)}")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")