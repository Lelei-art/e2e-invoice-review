from datetime import date, time
from decimal import Decimal
from typing import Literal

from pydantic import Field

from backend.app.schemas.shared import StrictSchema, TaxDetail


class ReceiptLineItem(StrictSchema):
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    field_confidence: dict[str, float] = Field(default_factory=dict)


class Receipt(StrictSchema):
    document_type: Literal["receipt"] = "receipt"
    source_model: Literal["prebuilt-receipt"] = "prebuilt-receipt"
    merchant_name: str | None = None
    merchant_address: str | None = None
    merchant_phone_number: str | None = None
    receipt_type: str | None = None
    country_region: str | None = None
    transaction_date: date | None = None
    transaction_time: time | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    total_tax: Decimal | None = None
    tip: Decimal | None = None
    total: Decimal | None = None
    line_items: list[ReceiptLineItem] = Field(default_factory=list)
    tax_details: list[TaxDetail] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
