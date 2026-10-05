from datetime import date, time
from decimal import Decimal

from pydantic import Field

from backend.app.schemas.shared import StrictSchema


class ReceiptExtractionLineItem(StrictSchema):
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    total_price: Decimal | None = None


class ReceiptExtractionTaxDetail(StrictSchema):
    description: str | None = None
    rate: Decimal | None = None
    amount: Decimal | None = None
    net_amount: Decimal | None = None


class ReceiptExtraction(StrictSchema):
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
    line_items: list[ReceiptExtractionLineItem] = Field(default_factory=list)
    tax_details: list[ReceiptExtractionTaxDetail] = Field(default_factory=list)
