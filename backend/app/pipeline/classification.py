from pathlib import Path

from backend.app.providers.azure_document_classifier import (
    classify_document as classify_with_azure_openai,
)
from backend.app.schemas.classification import DocumentClassification


async def classify_document(document_path: Path) -> DocumentClassification:
    return await classify_with_azure_openai(document_path)
