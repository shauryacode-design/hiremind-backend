from functools import lru_cache

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_tokenizer():
    return AutoTokenizer.from_pretrained(MODEL_NAME)


@lru_cache(maxsize=1)
def get_model():
    model_path = "models/all-MiniLM-L6-v2/model.onnx"

    return ort.InferenceSession(
        model_path,
        providers=["CPUExecutionProvider"],
    )


def generate_embedding(text: str) -> list[float]:
    tokenizer = get_tokenizer()
    model = get_model()

    inputs = tokenizer(
        text,
        padding=True,
        truncation=True,
        max_length=256,
        return_tensors="np",
    )

    outputs = model.run(
        None,
        {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64),
            "token_type_ids": inputs["token_type_ids"].astype(np.int64),
        },
    )

    token_embeddings = outputs[0]
    attention_mask = inputs["attention_mask"]

    mask = attention_mask[..., None]
    masked_embeddings = token_embeddings * mask

    embedding = masked_embeddings.sum(axis=1) / np.clip(
        mask.sum(axis=1),
        1e-9,
        None,
    )

    embedding = embedding[0]

    embedding = embedding / np.linalg.norm(embedding)

    return embedding.tolist()
