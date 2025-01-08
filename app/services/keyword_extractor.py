from bs4 import BeautifulSoup
from fastapi import HTTPException
import yake

def extract_data_from_html(html_content: str):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()
        
        # 썸네일 추출 
        og_image = soup.find('meta', property='og:image')
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        
        if og_image and og_image.get('content'):
            thumbnail = og_image['content']
        elif twitter_image and twitter_image.get('content'):
            thumbnail = twitter_image['content']
        else:
            thumbnail = "basetumbnail.jpg" # todo: 기본 썸네일 이미지
        
        language = "ko"  # 한국어 기준 (영어도 함께 처리 가능)
        max_ngram_size = 2 
        deduplication_threshold = 0.9
        num_of_keywords = 3

        kw_extractor = yake.KeywordExtractor(
            lan=language, 
            n=max_ngram_size, 
            dedupLim=deduplication_threshold, 
            top=num_of_keywords, 
            features=None
        )
        keywords = kw_extractor.extract_keywords(text)

        return {
            "thumbnail": thumbnail,
            "keywords": [kw for kw, score in keywords]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    