from bs4 import BeautifulSoup
from app.external.s3_service import download_html_from_s3
from app.utils.text_processing import extract_main_text, extract_keywords_tfidf

def extract_data_from_s3(id: str, s3_key: str):
    """s3 키를 입력받아 HTML에서 데이터 추출"""
    html_content = download_html_from_s3(s3_key)

    soup = BeautifulSoup(html_content, 'html.parser')
    og_image = soup.find('meta', property='og:image')
    
    if og_image and og_image.get('content'):
        thumbnail = og_image['content']
    else:
        thumbnail = "basetumbnail.jpg" # todo: 기본 썸네일 이미지

    main_text = extract_main_text(html_content)
    keywords = extract_keywords_tfidf(main_text)
    
    return {
        "image_url": thumbnail,
        "keywords": keywords
    }
