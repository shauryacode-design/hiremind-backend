from google import genai
from google.genai import errors
from pydantic import BaseModel

from app.config import GEMINI_API_KEY


client = genai.Client(api_key=GEMINI_API_KEY)

GEMINI_MODEL = "gemini-3.6-flash"


class GeminiServiceError(Exception):
    """Raised when Gemini cannot complete an AI request."""

    pass


def generate_structured(
    prompt: str,
    response_schema: type[BaseModel]
) -> BaseModel:

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_schema": response_schema,
            },
        )

        return response_schema.model_validate_json(response.text)

    except errors.ServerError as exc:
        raise GeminiServiceError(
            "Gemini is temporarily unavailable. Please try again in a moment."
        ) from exc

    except errors.APIError as exc:
        raise GeminiServiceError(
            "The AI service could not process this request. Please try again."
        ) from exc

    except Exception as exc:
        raise GeminiServiceError(
            "Failed to generate a valid AI response."
        ) from exc