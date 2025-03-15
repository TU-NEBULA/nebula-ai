import torch
import numpy as np
import requests
import logging
import sys
from transformers import AutoTokenizer, AutoModel

from app.core.config import settings

# ✅ Docker 및 Celery 환경에서도 로그가 출력되도록 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # stdout으로 로그 출력
    ]
)
logger = logging.getLogger(__name__)


class EmbeddingModel:
    MODEL_NAME = settings.MODEL_NAME
    CACHE_DIR = settings.CACHE_DIR
    USE_HF_API = settings.USE_HF_API
    HF_API_TOKEN = settings.HF_API_TOKEN

    def __init__(self, model_name: str = MODEL_NAME, cache_dir: str = CACHE_DIR):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        if self.USE_HF_API:
            logger.info("✅ Using Hugging Face Inference API")
        else:
            logger.info(f"✅ Loading local model: {model_name}")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
            self.model = AutoModel.from_pretrained(model_name, cache_dir=cache_dir)
            self.model.to(self.device)

    def get_embedding(self, text: str, prefix: str = "passage: ") -> np.ndarray:
        """
        문장을 E5 모델을 사용해 임베딩 벡터로 변환
        - AWS 배포 시 Hugging Face Inference API 사용
        - 로컬 테스트 시 로컬 모델 사용
        """
        prompt_text = f"{prefix}{text}"
        
        # ✅ Hugging Face API 사용 여부 로깅
        logger.info(f"🔍 self.USE_HF_API: {self.USE_HF_API}")

        if self.USE_HF_API:
            return self.get_embedding_from_hf_api(prompt_text)
        else:
            return self.get_embedding_from_local_model(prompt_text)

    def get_embedding_from_local_model(self, text: str) -> np.ndarray:
        """로컬 모델을 사용해 문장 임베딩"""
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        cls_embedding = outputs.last_hidden_state[:, 0, :]
        return cls_embedding.squeeze(0).cpu().numpy()

    def get_embedding_from_hf_api(self, text: str) -> np.ndarray:
        """Hugging Face Inference API를 사용해 문장 임베딩"""
        API_URL = f"https://api-inference.huggingface.co/models/{self.MODEL_NAME}"
        headers = {"Authorization": f"Bearer {self.HF_API_TOKEN}"}

        response = requests.post(API_URL, headers=headers, json={"inputs": text})
        
        if response.status_code == 200:
            logger.info("✅ Hugging Face API 호출 성공")
            return np.array(response.json()[0])
        else:
            logger.error(f"❌ Hugging Face API Error: {response.status_code}, {response.text}")
            raise ValueError(f"Hugging Face API Error: {response.status_code}, {response.text}")
