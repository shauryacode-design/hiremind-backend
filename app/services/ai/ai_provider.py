from pydantic import BaseModel

from app.services.ai.gemini import generate_structured as generate_gemini
from app.services.ai.gemini import GeminiServiceError


def generate_structured(
    prompt: str,
    response_schema: type[BaseModel],
) -> BaseModel:

    # 1. Try Gemini first
    try:
        print("AI Provider: Trying Gemini...")
        return generate_gemini(prompt, response_schema)

    except GeminiServiceError as gemini_error:
        print(f"Gemini failed: {gemini_error}")
        print("AI Provider: Falling back to Groq...")

    # 2. Groq fallback
    try:
        from app.services.ai.groq import generate_structured as generate_groq

        return generate_groq(prompt, response_schema)

    except Exception as groq_error:
        print(f"Groq failed: {groq_error}")

        raise RuntimeError(
            "All AI providers are currently unavailable."
        ) from groq_error