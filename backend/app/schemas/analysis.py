from pydantic import Field

from backend.app.schemas.invoice.extraction import InvoiceExtraction
from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.receipt.extraction import ReceiptExtraction
from backend.app.schemas.receipt.model import Receipt
from backend.app.schemas.shared import ExtractionConflict, FieldProvenance, StrictSchema


class InvoiceAnalysis(StrictSchema):
    document_intelligence: Invoice
    azure_openai: InvoiceExtraction
    merged: Invoice
    field_provenance: dict[str, FieldProvenance]
    conflicts: list[ExtractionConflict] = Field(default_factory=list)


class ReceiptAnalysis(StrictSchema):
    document_intelligence: Receipt
    azure_openai: ReceiptExtraction
    merged: Receipt
    field_provenance: dict[str, FieldProvenance]
    conflicts: list[ExtractionConflict] = Field(default_factory=list)
