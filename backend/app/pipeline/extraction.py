from pathlib import Path
from typing import Literal, overload

from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.receipt.model import Receipt
from backend.app.services.azure_openai_service import AzureOpenAIService


class DocumentIntelligenceExtractionStep:
    """Route a classification to the matching Document Intelligence model."""

    @overload
    def run(
        self, *, document_path: Path, document_type: Literal["invoice"]
    ) -> Invoice: ...

    @overload
    def run(
        self, *, document_path: Path, document_type: Literal["receipt"]
    ) -> Receipt: ...

    def run(
        self,
        *,
        document_path: Path,
        document_type: Literal["invoice", "receipt"],
    ) -> Invoice | Receipt:
        service = AzureOpenAIService()
        try:
            if document_type == "invoice":
                return service.analyze_invoice(document_path).merged
            return service.analyze_receipt(document_path).merged
        finally:
            service.close()
