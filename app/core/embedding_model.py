from transformers import AutoTokenizer, AutoModel
import torch

MODEL_NAME = "intfloat/multilingual-e5-large-instruct"
CACHE_DIR = "./models"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=CACHE_DIR)
model = AutoModel.from_pretrained(MODEL_NAME, cache_dir=CACHE_DIR)

device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

def get_embedding(text: str) -> list:
    """입력된 HTML 문자열을 임베딩 변환"""
    formatted_text = f"query: {text}"
    inputs = tokenizer(formatted_text, return_tensors="pt", padding=True, truncation=True)
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    return embedding.tolist()
