from app.core.embedding_model import get_embedding
from app.external.s3_service import download_html_from_s3
from app.utils.text_processing import extract_main_text, split_sentences

def generate_embedding_from_s3(id: str, s3_key: str):
    """s3 키를 입력받아 HTML 문자열 임베딩 변환"""

    html_content = download_html_from_s3(s3_key)
        
    main_text = extract_main_text(html_content)
    main_text_embs = get_embedding(main_text)

    sentences = split_sentences(main_text)
    sentence_embs = [get_embedding(s, prefix="passage: ") for s in sentences]


    return {
        "id": id,
        "main_text": main_text,
        "main_text_embs": main_text_embs.tolist(),
        "sentences": sentences,
        "sentence_embs": [e.tolist() for e in sentence_embs]
    }
