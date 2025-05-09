import os
import numpy as np
import requests
from app.core.config import settings
class EmbeddingModel:
    """
    Hugging Face Inference API 를 사용해 텍스트 임베딩을 가져오는 클래스.
    """

    API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{settings.EMBEDDING_MODEL_NAME}"
    TOKEN = settings.HUGGINGFACE_API_TOKEN

    def __init__(self):
        if not self.TOKEN:
            raise ValueError("Hugging Face API 토큰이 설정되지 않았습니다.")
        self.headers = {
            "Authorization": f"Bearer {self.TOKEN}",
            "Content-Type": "application/json"
        }

    def get_embedding(self, text: str, prefix: str = "passage: ") -> np.ndarray:
        """
        HF Inference API에 POST 요청하여 임베딩을 (hidden_size,) 형태로 반환.
        """
        payload = {
            "inputs": f"{prefix}{text}",
            # E5 모델 특성에 따라 추가 옵션(ex. truncation)을 줄 수도 있습니다.
        }
        resp = requests.post(self.API_URL, headers=self.headers, json=payload, timeout=30)
        resp.raise_for_status()

        # API가 [[...]] 형태로 리턴하므로 첫번째 벡터를 취함
        embedding = np.array(resp.json()[0], dtype=np.float32)
        return embedding

