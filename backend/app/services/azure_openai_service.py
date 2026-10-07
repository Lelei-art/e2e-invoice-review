import json
from pathlib import Path
from typing import overload

from pydantic import BaseModel

from backend.app.providers.azure_openai import (
    MODEL_NAME,
    AzureOpenAIProvider,
    AzureOpenAIRequestError,
)
from backend.app.schemas.analysis import InvoiceAnalysis, ReceiptAnalysis
from backend.app.schemas.invoice.extraction import InvoiceExtraction
from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.receipt.extraction import ReceiptExtraction
from backend.app.schemas.receipt.model import Receipt
from backend.app.schemas.shared import ExtractionConflict, FieldProvenance
from backend.app.services.document_intelligence_service import (
    DocumentIntelligenceService,
)

__all__ = ["AzureOpenAIRequestError", "AzureOpenAIService"]


class AzureOpenAIService:
    model_name = MODEL_NAME

    def __init__(self) -> None:
        self._provider = AzureOpenAIProvider()
        self._document_intelligence: DocumentIntelligenceService | None = None

    def analyze_invoice(self, document_path: Path) -> InvoiceAnalysis:
        document_intelligence = self._get_document_intelligence().extract_invoice(
            document_path
        )
        azure_openai = self._provider.analyze_document(
            document_path,
            instructions=(
                "Extract the invoice fields from the provided document. Use only values "
                "visible in the document. Return null for missing or uncertain scalar "
                "fields and an empty list when there are no readable line items or tax "
                "details. For amount_due, capture the remaining balance payable only when "
                "the invoice explicitly shows it; distinguish it from invoice_total and "
                "do not copy the invoice total into amount_due. Do not infer values or "
                "decide whether the invoice is valid."
            ),
            response_format=InvoiceExtraction,
        )
        merged, provenance, conflicts = _merge(
            document_intelligence, azure_openai
        )
        merged = merged.model_copy(
            update={"field_provenance": provenance, "conflicts": conflicts}
        )
        return InvoiceAnalysis(
            document_intelligence=document_intelligence,
            azure_openai=azure_openai,
            merged=merged,
            field_provenance=provenance,
            conflicts=conflicts,
        )

    def analyze_receipt(self, document_path: Path) -> ReceiptAnalysis:
        document_intelligence = self._get_document_intelligence().extract_receipt(
            document_path
        )
        azure_openai = self._provider.analyze_document(
            document_path,
            instructions=(
                "Extract the receipt fields from the provided document. Use only values "
                "visible in the document. Return null for missing or uncertain scalar "
                "fields and an empty list when there are no readable line items or tax "
                "details. Do not infer values or decide whether the receipt is valid."
            ),
            response_format=ReceiptExtraction,
        )
        merged, provenance, conflicts = _merge(
            document_intelligence, azure_openai
        )
        merged = merged.model_copy(
            update={"field_provenance": provenance, "conflicts": conflicts}
        )
        return ReceiptAnalysis(
            document_intelligence=document_intelligence,
            azure_openai=azure_openai,
            merged=merged,
            field_provenance=provenance,
            conflicts=conflicts,
        )

    def generate_response(self, prompt: str) -> str:
        return self._provider.generate_response(prompt)

    def generate_response_with_dump(
        self, prompt: str
    ) -> tuple[str, dict[str, object]]:
        return self._provider.generate_response_with_dump(prompt)

    def close(self) -> None:
        try:
            self._provider.close()
        finally:
            if self._document_intelligence is not None:
                self._document_intelligence.close()

    def _get_document_intelligence(self) -> DocumentIntelligenceService:
        if self._document_intelligence is None:
            self._document_intelligence = DocumentIntelligenceService()
        return self._document_intelligence


@overload
def _merge(
    document_intelligence: Invoice, azure_openai: InvoiceExtraction
) -> tuple[Invoice, dict[str, FieldProvenance], list[ExtractionConflict]]: ...


@overload
def _merge(
    document_intelligence: Receipt, azure_openai: ReceiptExtraction
) -> tuple[Receipt, dict[str, FieldProvenance], list[ExtractionConflict]]: ...


def _merge(
    document_intelligence: Invoice | Receipt,
    azure_openai: InvoiceExtraction | ReceiptExtraction,
) -> tuple[Invoice | Receipt, dict[str, FieldProvenance], list[ExtractionConflict]]:
    if isinstance(document_intelligence, Invoice) != isinstance(
        azure_openai, InvoiceExtraction
    ):
        raise TypeError("Document Intelligence and Azure OpenAI schemas must match.")

    merged_data = document_intelligence.model_dump(mode="python")
    primary_data = document_intelligence.model_dump(mode="python")
    ai_data = azure_openai.model_dump(mode="python")
    provenance: dict[str, FieldProvenance] = {}
    conflicts: list[ExtractionConflict] = []

    for field, ai_value in ai_data.items():
        primary_value = primary_data[field]
        if _has_value(primary_value):
            provenance[field] = FieldProvenance(source="document_intelligence")
            if _has_value(ai_value) and _comparable(primary_value) != _comparable(ai_value):
                conflicts.append(
                    ExtractionConflict(
                        field=field,
                        document_intelligence_value=_display(primary_value),
                        azure_openai_value=_display(ai_value),
                    )
                )
        elif _has_value(ai_value):
            merged_data[field] = ai_value
            provenance[field] = FieldProvenance(source="azure_openai")
        else:
            provenance[field] = FieldProvenance(source="missing")

    return type(document_intelligence).model_validate(merged_data), provenance, conflicts


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return bool(value)
    return True


def _comparable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_comparable(item) for item in value]
    if isinstance(value, dict):
        return {key: _comparable(item) for key, item in value.items()}
    return value


def _display(value: object) -> str:
    return json.dumps(_comparable(value), ensure_ascii=False, default=str)
