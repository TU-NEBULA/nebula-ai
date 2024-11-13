import requests
from bs4 import BeautifulSoup
from fastapi import HTTPException
import yake

def extract_keywords_from_url(url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()
        
        language = "ko"  # 한국어 기준 (영어도 함께 처리 가능)
        max_ngram_size = 2  # 1-gram과 2-gram 고려
        deduplication_threshold = 0.9
        num_of_keywords = 10

        kw_extractor = yake.KeywordExtractor(
            lan=language, 
            n=max_ngram_size, 
            dedupLim=deduplication_threshold, 
            top=num_of_keywords, 
            features=None
        )
        keywords = kw_extractor.extract_keywords(text)

        return {
            "keywords": [{"keyword": kw, "score": score} for kw, score in keywords]
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error fetching URL: {str(e)}")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")