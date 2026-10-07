from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field

from backend.app.schemas.shared import (
    ExtractionConflict,
    FieldProvenance,
    StrictSchema,
    TaxDetail,
)


class InvoiceLineItem(StrictSchema):
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None
    field_confidence: dict[str, float] = Field(default_factory=dict)


class Invoice(StrictSchema):
    document_type: Literal["invoice"] = "invoice"
    source_model: Literal["prebuilt-invoice"] = "prebuilt-invoice"
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    purchase_order: str | None = None
    vendor_name: str | None = None
    vendor_address: str | None = None
    vendor_vat_id: str | None = None
    customer_name: str | None = None
    customer_address: str | None = None
    customer_vat_id: str | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    total_tax: Decimal | None = None
    invoice_total: Decimal | None = None
    amount_due: Decimal | None = None
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    tax_details: list[TaxDetail] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    field_provenance: dict[str, FieldProvenance] = Field(default_factory=dict)
    conflicts: list[ExtractionConflict] = Field(default_factory=list)
