from bs4 import BeautifulSoup

def extract_thumbnail(html_content: str) -> str:
    """
    HTML 콘텐츠에서 썸네일 URL을 추출합니다.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    og_image = soup.find('meta', property='og:image')
    
    if og_image and og_image.get('content'):
        return og_image['content']
    else:
        return "basetumbnail.jpg"  # todo: 기본 썸네일 이미지
    