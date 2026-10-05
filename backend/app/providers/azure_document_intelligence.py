from collections.abc import Mapping
from datetime import date, time
from decimal import Decimal

from azure.ai.documentintelligence.models import AnalyzeResult, DocumentField

from backend.app.schemas.invoice.model import Invoice, InvoiceLineItem
from backend.app.schemas.receipt.model import Receipt, ReceiptLineItem
from backend.app.schemas.shared import TaxDetail


def map_invoice_result(result: AnalyzeResult) -> Invoice:
    document = _first_document(result, "prebuilt-invoice")
    fields = document.fields or {}
    return Invoice(
        currency=_currency(fields, ("InvoiceTotal", "SubTotal", "TotalTax")),
        invoice_number=_text(fields, "InvoiceId"),
        invoice_date=_date(fields, "InvoiceDate"),
        due_date=_date(fields, "DueDate"),
        purchase_order=_text(fields, "PurchaseOrder"),
        vendor_name=_text(fields, "VendorName"),
        vendor_address=_text(fields, "VendorAddress"),
        vendor_vat_id=_text(fields, "VendorTaxId"),
        customer_name=_text(fields, "CustomerName"),
        customer_address=_text(fields, "CustomerAddress"),
        customer_vat_id=_text(fields, "CustomerTaxId"),
        subtotal=_amount(fields, "SubTotal"),
        total_tax=_amount(fields, "TotalTax"),
        invoice_total=_amount(fields, "InvoiceTotal"),
        amount_due=_amount(fields, "AmountDue"),
        line_items=_invoice_items(fields),
        tax_details=_tax_details(fields),
        field_confidence=_confidences(
            fields,
            {
                "invoice_number": "InvoiceId",
                "invoice_date": "InvoiceDate",
                "due_date": "DueDate",
                "purchase_order": "PurchaseOrder",
                "vendor_name": "VendorName",
                "vendor_address": "VendorAddress",
                "vendor_vat_id": "VendorTaxId",
                "customer_name": "CustomerName",
                "customer_address": "CustomerAddress",
                "customer_vat_id": "CustomerTaxId",
                "subtotal": "SubTotal",
                "total_tax": "TotalTax",
                "invoice_total": "InvoiceTotal",
                "amount_due": "AmountDue",
            },
        ),
    )


def map_receipt_result(result: AnalyzeResult) -> Receipt:
    document = _first_document(result, "prebuilt-receipt")
    fields = document.fields or {}
    return Receipt(
        currency=_currency(fields, ("Total", "Subtotal", "TotalTax")),
        merchant_name=_text(fields, "MerchantName"),
        merchant_address=_text(fields, "MerchantAddress"),
        merchant_phone_number=_text(fields, "MerchantPhoneNumber"),
        receipt_type=_text(fields, "ReceiptType"),
        country_region=_text(fields, "CountryRegion"),
        transaction_date=_date(fields, "TransactionDate"),
        transaction_time=_time(fields, "TransactionTime"),
        subtotal=_amount(fields, "Subtotal"),
        total_tax=_amount(fields, "TotalTax"),
        tip=_amount(fields, "Tip"),
        total=_amount(fields, "Total"),
        line_items=_receipt_items(fields),
        tax_details=_tax_details(fields),
        field_confidence=_confidences(
            fields,
            {
                "merchant_name": "MerchantName",
                "merchant_address": "MerchantAddress",
                "merchant_phone_number": "MerchantPhoneNumber",
                "receipt_type": "ReceiptType",
                "country_region": "CountryRegion",
                "transaction_date": "TransactionDate",
                "subtotal": "Subtotal",
                "total_tax": "TotalTax",
                "tip": "Tip",
                "total": "Total",
            },
        ),
    )


def _first_document(result: AnalyzeResult, expected_model: str):
    if result.model_id != expected_model:
        raise ValueError(
            f"Expected Document Intelligence model {expected_model!r}, "
            f"got {result.model_id!r}."
        )
    if not result.documents:
        raise ValueError(f"Document Intelligence returned no documents for {expected_model}.")
    return result.documents[0]


def _field(fields: Mapping[str, DocumentField], name: str) -> DocumentField | None:
    return fields.get(name)


def _text(fields: Mapping[str, DocumentField], name: str) -> str | None:
    field = _field(fields, name)
    if field is None:
        return None
    return (
        field.value_string
        or field.value_phone_number
        or field.value_country_region
        or field.content
    )


def _date(fields: Mapping[str, DocumentField], name: str) -> date | None:
    field = _field(fields, name)
    return field.value_date if field is not None else None


def _time(fields: Mapping[str, DocumentField], name: str) -> time | None:
    field = _field(fields, name)
    return field.value_time if field is not None else None


def _amount(fields: Mapping[str, DocumentField], name: str) -> Decimal | None:
    field = _field(fields, name)
    if field is None:
        return None
    if field.value_currency is not None:
        amount = field.value_currency.amount
        return Decimal(str(amount)) if amount is not None else None
    if field.value_number is not None:
        return Decimal(str(field.value_number))
    if field.value_integer is not None:
        return Decimal(field.value_integer)
    return None


def _currency(
    fields: Mapping[str, DocumentField], names: tuple[str, ...]
) -> str | None:
    for name in names:
        field = _field(fields, name)
        if field is not None and field.value_currency is not None:
            currency_code = field.value_currency.currency_code
            if currency_code:
                return currency_code
    return None


def _invoice_items(
    fields: Mapping[str, DocumentField],
) -> list[InvoiceLineItem]:
    return [
        InvoiceLineItem(
            description=_text(item, "Description"),
            quantity=_amount(item, "Quantity"),
            unit=_text(item, "Unit"),
            unit_price=_amount(item, "UnitPrice"),
            amount=_amount(item, "Amount"),
            field_confidence=_confidences(
                item,
                {
                    "description": "Description",
                    "quantity": "Quantity",
                    "unit": "Unit",
                    "unit_price": "UnitPrice",
                    "amount": "Amount",
                },
            ),
        )
        for item in _array_items(fields, "Items")
    ]


def _receipt_items(
    fields: Mapping[str, DocumentField],
) -> list[ReceiptLineItem]:
    return [
        ReceiptLineItem(
            description=_text(item, "Description"),
            quantity=_amount(item, "Quantity"),
            unit=_text(item, "QuantityUnit"),
            unit_price=_amount(item, "Price"),
            total_price=_amount(item, "TotalPrice"),
            field_confidence=_confidences(
                item,
                {
                    "description": "Description",
                    "quantity": "Quantity",
                    "unit": "QuantityUnit",
                    "unit_price": "Price",
                    "total_price": "TotalPrice",
                },
            ),
        )
        for item in _array_items(fields, "Items")
    ]


def _array_items(
    fields: Mapping[str, DocumentField], name: str
) -> list[Mapping[str, DocumentField]]:
    field = _field(fields, name)
    if field is None or field.value_array is None:
        return []
    return [item.value_object for item in field.value_array if item.value_object is not None]


def _tax_details(fields: Mapping[str, DocumentField]) -> list[TaxDetail]:
    details = []
    for item in _array_items(fields, "TaxDetails"):
        rate = _amount(item, "Rate")
        rate_text = _text(item, "Rate")
        if rate is None and rate_text is not None and rate_text.endswith("%"):
            rate = Decimal(rate_text.removesuffix("%").strip()) / Decimal("100")
        details.append(
            TaxDetail(
                description=_text(item, "Description"),
                rate=rate,
                amount=_amount(item, "Amount"),
                net_amount=_amount(item, "NetAmount"),
                field_confidence=_confidences(
                    item,
                    {
                        "description": "Description",
                        "rate": "Rate",
                        "amount": "Amount",
                        "net_amount": "NetAmount",
                    },
                ),
            )
        )
    return details


def _confidences(
    fields: Mapping[str, DocumentField], names: Mapping[str, str]
) -> dict[str, float]:
    return {
        normalized_name: field.confidence
        for normalized_name, provider_name in names.items()
        if (field := _field(fields, provider_name)) is not None
        and field.confidence is not None
    }
