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


# import torch
# import numpy as np
# from transformers import AutoTokenizer, AutoModel
# from app.core.config import settings


# class EmbeddingModel:
#     MODEL_NAME = settings.MODEL_NAME
#     CACHE_DIR = settings.CACHE_DIR

#     def __init__(self, model_name: str = MODEL_NAME, cache_dir: str = CACHE_DIR):
#         self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#         self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
#         self.model = AutoModel.from_pretrained(model_name, cache_dir=cache_dir)
#         self.model.to(self.device)

#     def get_embedding(self, text: str, prefix: str = "passage: ") -> np.ndarray:
#         """
#         E5 모델을 사용해 단일 문자열의 임베딩을 구하여 (hidden_size,) 형태의 넘파이 배열로 반환.
#         """
#         prompt_text = f"{prefix}{text}"
#         inputs = self.tokenizer(prompt_text, return_tensors="pt", truncation=True)
#         inputs = {k: v.to(self.device) for k, v in inputs.items()}

#         with torch.no_grad():
#             outputs = self.model(**inputs)

#         cls_embedding = outputs.last_hidden_state[:, 0, :]
#         return cls_embedding.squeeze(0).cpu().numpy()
