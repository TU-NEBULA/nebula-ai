import torch
import numpy as np

from transformers import AutoTokenizer, AutoModel

MODEL_NAME = "intfloat/multilingual-e5-large-instruct"
CACHE_DIR = "./models"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=CACHE_DIR)
model = AutoModel.from_pretrained(MODEL_NAME, cache_dir=CACHE_DIR)

device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

def get_embedding(text: str, prefix="passage: ") -> np.ndarray:
    """
    E5 모델을 사용해 단일 문자열의 임베딩을 구하여 (hidden_size,) 형태의 넘파이 배열로 반환.
    """
    prompt_text = f"{prefix}{text}"
    inputs = tokenizer(prompt_text, return_tensors="pt", truncation=True)
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    cls_embedding = outputs.last_hidden_state[:, 0, :]
    return cls_embedding.squeeze(0).cpu().numpy()
