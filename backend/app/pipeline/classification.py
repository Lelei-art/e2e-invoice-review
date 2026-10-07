from pathlib import Path

from backend.app.providers.azure_document_classifier import (
    classify_document as classify_with_azure_openai,
)
from backend.app.schemas.classification import DocumentClassification


class DocumentClassificationStep:
    """Pipeline step that sends a local document to the configured classifier."""

    async def run(self, *, document_path: Path) -> DocumentClassification:
        """Classify `document_path` and return the provider-independent Pydantic result."""
        return await classify_with_azure_openai(document_path=document_path)
