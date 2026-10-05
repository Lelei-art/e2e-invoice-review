import base64
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AuthenticationError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app.schemas.shared import StrictSchema

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MODEL_NAME = "grok-4.6"
T = TypeVar("T", bound=StrictSchema)


class AzureOpenAIRequestError(Exception):
    def __init__(self, category: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code


class AzureOpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_openai_endpoint: str
    azure_openai_api_key: SecretStr


class AzureOpenAIProvider:
    def __init__(self) -> None:
        settings = AzureOpenAISettings()
        self._api_key = settings.azure_openai_api_key.get_secret_value()
        self._client = OpenAI(
            base_url=settings.azure_openai_endpoint,
            api_key=self._api_key,
        )

    def generate_response(self, prompt: str) -> str:
        answer, _ = self.generate_response_with_dump(prompt)
        return answer

    def generate_response_with_dump(self, prompt: str) -> tuple[str, dict[str, object]]:
        response = self._request(
            lambda: self._client.responses.create(
                model=MODEL_NAME,
                input=prompt,
            )
        )
        return response.output_text, response.model_dump(mode="json")

    def analyze_document(
        self,
        document_path: Path,
        *,
        instructions: str,
        response_format: type[T],
    ) -> T:
        if not document_path.is_file():
            raise FileNotFoundError(f"Document not found: {document_path}")

        media_type = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
        }.get(document_path.suffix.lower())
        if media_type is None:
            raise ValueError("Document must be a PDF, PNG, or JPEG file.")

        document_bytes = document_path.read_bytes()
        if not document_bytes:
            raise ValueError(f"Document is empty: {document_path}")

        encoded_document = base64.b64encode(document_bytes).decode("ascii")
        if media_type == "application/pdf":
            document_input: dict[str, str] = {
                "type": "input_file",
                "filename": document_path.name,
                "file_data": f"data:{media_type};base64,{encoded_document}",
            }
        else:
            document_input = {
                "type": "input_image",
                "image_url": f"data:{media_type};base64,{encoded_document}",
                "detail": "auto",
            }

        response = self._request(
            lambda: self._client.responses.parse(
                model=MODEL_NAME,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": instructions},
                            document_input,
                        ],
                    }
                ],
                text_format=response_format,
            )
        )
        if response.output_parsed is None:
            raise AzureOpenAIRequestError(
                "Structured response error",
                "The model did not return a structured document extraction.",
            )
        return response.output_parsed

    def _request(self, operation: Callable[[], T]) -> T:
        try:
            return operation()
        except AuthenticationError as error:
            raise self._request_error(
                "Authentication error",
                "Authentication failed. Check the configured API credential.",
                error,
            ) from None
        except PermissionDeniedError as error:
            raise self._request_error(
                "Permission error",
                "The configured credential does not have permission to use this model.",
                error,
            ) from None
        except RateLimitError as error:
            detail = self._error_detail(error).lower()
            if "insufficient_quota" in detail or "quota" in detail:
                message = "The Azure OpenAI resource has insufficient quota."
                category = "Quota error"
            else:
                message = "The request was rate limited. Wait briefly and try again."
                category = "Rate limit error"
            raise self._request_error(category, message, error) from None
        except APIConnectionError:
            raise AzureOpenAIRequestError(
                "Connection error",
                "Could not connect to the configured Azure OpenAI endpoint.",
            ) from None
        except APIStatusError as error:
            message = self._error_detail(error)
            raise self._request_error("API error", message, error) from None
        except APIError as error:
            raise AzureOpenAIRequestError(
                "API error",
                self._redact(str(error)),
            ) from None

    def close(self) -> None:
        self._client.close()

    def _request_error(
        self, category: str, message: str, error: APIStatusError
    ) -> AzureOpenAIRequestError:
        return AzureOpenAIRequestError(
            category,
            self._redact(message),
            status_code=error.status_code,
        )

    def _error_detail(self, error: APIStatusError) -> str:
        body = error.body
        if isinstance(body, dict):
            error_body = body.get("error")
            if isinstance(error_body, dict):
                code = error_body.get("code")
                message = error_body.get("message")
                details = [str(item) for item in (code, message) if item]
                if details:
                    return self._redact(": ".join(details))
        return self._redact(error.message)

    def _redact(self, message: str) -> str:
        return message.replace(self._api_key, "[REDACTED]") if self._api_key else message
