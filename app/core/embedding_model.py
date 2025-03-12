import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from app.core.config import settings


class EmbeddingModel:
    MODEL_NAME = settings.MODEL_NAME
    CACHE_DIR = settings.CACHE_DIR

    def __init__(self, model_name: str = MODEL_NAME, cache_dir: str = CACHE_DIR):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        self.model = AutoModel.from_pretrained(model_name, cache_dir=cache_dir)
        self.model.to(self.device)

    def get_embedding(self, text: str, prefix: str = "passage: ") -> np.ndarray:
        """
        E5 모델을 사용해 단일 문자열의 임베딩을 구하여 (hidden_size,) 형태의 넘파이 배열로 반환.
        """
        prompt_text = f"{prefix}{text}"
        inputs = self.tokenizer(prompt_text, return_tensors="pt", truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        cls_embedding = outputs.last_hidden_state[:, 0, :]
        return cls_embedding.squeeze(0).cpu().numpy()
