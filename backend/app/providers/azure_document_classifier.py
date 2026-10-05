from pathlib import Path

from openai import AsyncOpenAI
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.app.providers.azure_openai import (
    MODEL_NAME,
    AzureOpenAISettings,
)
from backend.app.schemas.classification import DocumentClassification

DOCUMENT_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


async def classify_document(document_path: Path) -> DocumentClassification:
    if not document_path.is_file():
        raise FileNotFoundError(f"Document not found: {document_path}")

    media_type = DOCUMENT_MEDIA_TYPES.get(document_path.suffix.lower())
    if media_type is None:
        raise ValueError("Document must be a PDF, PNG, or JPEG file.")

    document_bytes = document_path.read_bytes()
    if not document_bytes:
        raise ValueError(f"Document is empty: {document_path}")

    settings = AzureOpenAISettings()
    async with AsyncOpenAI(
        base_url=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key.get_secret_value(),
    ) as client:
        model = OpenAIResponsesModel(
            MODEL_NAME,
            provider=OpenAIProvider(openai_client=client),
        )
        agent = Agent(
            model,
            output_type=DocumentClassification,
            instructions=(
                "Classify the supplied original document as an invoice, receipt, or other. "
                "Use the visual document content, including text in any language. Choose "
                "other when it is unsupported or you are uncertain. Return only the "
                "classification and a concise reason; do not extract financial fields."
            ),
        )
        result = await agent.run(
            [
                "Classify this document.",
                BinaryContent(data=document_bytes, media_type=media_type),
            ]
        )
        return result.output
