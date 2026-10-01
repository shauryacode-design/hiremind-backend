from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

# embeddings.py is in app/services/ai/, so parents[3] is the project root
MODEL_DIR = Path(__file__).resolve().parents[3] / "models" / "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_tokenizer():
    tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=256)
    return tokenizer


@lru_cache(maxsize=1)
def get_model():
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False

    return ort.InferenceSession(
        str(MODEL_DIR / "model.onnx"),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )


def generate_embedding(text: str) -> list[float]:
    tokenizer = get_tokenizer()
    model = get_model()

    encoded = tokenizer.encode(text)

    input_ids = np.array([encoded.ids], dtype=np.int64)
    attention_mask = np.array([encoded.attention_mask], dtype=np.int64)
    token_type_ids = np.array([encoded.type_ids], dtype=np.int64)

    outputs = model.run(
        None,
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        },
    )

    token_embeddings = outputs[0]

    mask = attention_mask[..., None]
    masked_embeddings = token_embeddings * mask
    embedding = masked_embeddings.sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)

    embedding = embedding[0]
    embedding = embedding / np.linalg.norm(embedding)

    return embedding.tolist()