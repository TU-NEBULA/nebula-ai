"""
썸네일 추출 모듈

이 모듈은 HTML 콘텐츠에서 썸네일 이미지를 추출하는 기능을 제공합니다.
"""
from bs4 import BeautifulSoup

def extract_thumbnail(html_content: str) -> str:
    """
    HTML 콘텐츠에서 썸네일 URL을 추출합니다.

    Args:
        html_content (str): HTML 콘텐츠
    Returns:
        str: 추출된 썸네일 URL, 없을 경우 기본 썸네일 이미지 경로 반환
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    og_image = soup.find('meta', property='og:image')
    
    if og_image and og_image.get('content'):
        return og_image['content']
    else:
        return "basetumbnail.jpg" 
    