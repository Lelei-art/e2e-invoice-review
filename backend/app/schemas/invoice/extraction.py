from datetime import date
from decimal import Decimal

from pydantic import Field

from backend.app.schemas.shared import StrictSchema


class InvoiceExtractionLineItem(StrictSchema):
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class InvoiceExtractionTaxDetail(StrictSchema):
    description: str | None = None
    rate: Decimal | None = None
    amount: Decimal | None = None
    net_amount: Decimal | None = None


class InvoiceExtraction(StrictSchema):
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
    line_items: list[InvoiceExtractionLineItem] = Field(default_factory=list)
    tax_details: list[InvoiceExtractionTaxDetail] = Field(default_factory=list)
