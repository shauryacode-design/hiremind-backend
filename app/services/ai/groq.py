import json

from groq import Groq
from pydantic import BaseModel

from app.config import GROQ_API_KEY


client = Groq(api_key=GROQ_API_KEY)

GROQ_MODEL = "openai/gpt-oss-20b"


def generate_structured(
    prompt: str,
    response_schema: type[BaseModel],
) -> BaseModel:

    schema = response_schema.model_json_schema()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.2,
        max_completion_tokens=1600,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": response_schema.__name__,
                "schema": schema,
            },
        },
    )

    content = response.choices[0].message.content

    return response_schema.model_validate(json.loads(content))