import hashlib
import json
from decimal import Decimal

from stdnum.eu import vat

from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.receipt.model import Receipt
from backend.app.schemas.validation import ValidationFinding

type FinancialDocument = Invoice | Receipt
NORTHSTAR_VAT_ID = "NL00449544B01"
TOTAL_TOLERANCE = Decimal("0.01")
LOW_CONFIDENCE_THRESHOLD = 0.80


def validate_document(document: FinancialDocument) -> list[ValidationFinding]:
    if isinstance(document, Invoice):
        return validate_invoice(document)
    return validate_receipt(document)


def validate_invoice(invoice: Invoice) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for field, label, value in (
        ("vendor_name", "Supplier", invoice.vendor_name),
        ("customer_name", "Customer", invoice.customer_name),
        ("invoice_number", "Invoice number", invoice.invoice_number),
        ("invoice_date", "Invoice date", invoice.invoice_date),
        ("invoice_total", "Invoice total", invoice.invoice_total),
        ("currency", "Currency", invoice.currency),
    ):
        if value is None or (isinstance(value, str) and not value.strip()):
            findings.append(_missing(field, f"{label} is missing."))

    if not invoice.vendor_vat_id:
        findings.append(
            _error(
                "vendor_vat_id_required",
                "vendor_vat_id",
                "Supplier VAT number is missing.",
            )
        )
    elif not vat.is_valid(invoice.vendor_vat_id):
        findings.append(
            _error(
                "vendor_vat_id_invalid",
                "vendor_vat_id",
                "Supplier VAT number has an invalid EU format or checksum.",
            )
        )

    if not invoice.customer_vat_id:
        findings.append(_missing("customer_vat_id", "Customer VAT number is missing."))
    elif not vat.is_valid(invoice.customer_vat_id):
        findings.append(
            _error(
                "customer_vat_id_invalid",
                "customer_vat_id",
                "Customer VAT number has an invalid EU format or checksum.",
            )
        )
    elif _normalize_identifier(invoice.customer_vat_id) != _normalize_identifier(
        NORTHSTAR_VAT_ID
    ):
        findings.append(
            _error(
                "customer_vat_id_mismatch",
                "customer_vat_id",
                "Customer VAT number does not match Northstar Facilities B.V.",
            )
        )

    if invoice.invoice_total is not None and invoice.invoice_total <= 0:
        findings.append(
            _error(
                "invoice_total_not_positive",
                "invoice_total",
                "Invoice total must be greater than zero.",
            )
        )
    if (
        invoice.invoice_date is not None
        and invoice.due_date is not None
        and invoice.due_date < invoice.invoice_date
    ):
        findings.append(
            _error(
                "invoice_date_order_invalid",
                "due_date",
                "Due date cannot be earlier than the invoice date.",
            )
        )
    if (
        invoice.subtotal is not None
        and invoice.total_tax is not None
        and invoice.invoice_total is not None
        and abs(invoice.subtotal + invoice.total_tax - invoice.invoice_total)
        > TOTAL_TOLERANCE
    ):
        findings.append(
            _error(
                "invoice_total_mismatch",
                "invoice_total",
                "Subtotal plus VAT does not match the invoice total.",
            )
        )
    if not invoice.purchase_order:
        findings.append(
            _warning("purchase_order_missing", "purchase_order", "Purchase order is missing.")
        )
    findings.extend(_low_confidence_findings(invoice))
    return findings


def validate_receipt(receipt: Receipt) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    for field, label, value in (
        ("merchant_name", "Merchant", receipt.merchant_name),
        ("transaction_date", "Transaction date", receipt.transaction_date),
        ("currency", "Currency", receipt.currency),
        ("total", "Receipt total", receipt.total),
        ("total_tax", "VAT total", receipt.total_tax),
    ):
        if value is None or (isinstance(value, str) and not value.strip()):
            findings.append(_missing(field, f"{label} is missing."))

    if receipt.total is not None and receipt.total <= 0:
        findings.append(
            _error(
                "receipt_total_not_positive",
                "total",
                "Receipt total must be greater than zero.",
            )
        )
    if (
        receipt.subtotal is not None
        and receipt.total_tax is not None
        and receipt.total is not None
        and abs(
            receipt.subtotal
            + receipt.total_tax
            + (receipt.tip or Decimal("0"))
            - receipt.total
        )
        > TOTAL_TOLERANCE
    ):
        findings.append(
            _error(
                "receipt_total_mismatch",
                "total",
                "Subtotal plus VAT and tip does not match the receipt total.",
            )
        )
    findings.extend(_low_confidence_findings(receipt))
    return findings


def duplicate_finding(document: FinancialDocument) -> ValidationFinding:
    if isinstance(document, Invoice):
        return _error(
            "duplicate_invoice",
            "invoice_number",
            "An invoice with the same supplier VAT number and invoice number was processed before.",
        )
    return _warning(
        "possible_duplicate_receipt",
        "total",
        "A receipt with the same merchant, date, currency, and total was processed "
        "before; review it for duplication.",
    )


def supplier_fixable_findings(
    findings: list[ValidationFinding],
) -> list[ValidationFinding]:
    supplier_fields = {
        "vendor_name",
        "vendor_vat_id",
        "customer_name",
        "customer_vat_id",
        "invoice_number",
        "invoice_date",
        "due_date",
        "purchase_order",
        "currency",
        "subtotal",
        "total_tax",
        "invoice_total",
        "amount_due",
        "merchant_name",
        "transaction_date",
        "total",
    }
    return [
        finding
        for finding in findings
        if finding.field in supplier_fields
        and finding.code not in {"duplicate_invoice", "possible_duplicate_receipt"}
        and (finding.severity == "error" or finding.code == "purchase_order_missing")
    ]


def duplicate_fingerprint(document: FinancialDocument) -> str | None:
    if isinstance(document, Invoice):
        identity = _normalize_identifier(document.vendor_vat_id or "")
        invoice_number = _normalize_identifier(document.invoice_number or "")
        if not identity or not invoice_number:
            return None
        signature = ("invoice", identity, invoice_number)
    else:
        merchant = _normalize_identifier(document.merchant_name or "")
        if (
            not merchant
            or document.transaction_date is None
            or not document.currency
            or document.total is None
        ):
            return None
        signature = (
            "receipt",
            merchant,
            document.transaction_date.isoformat(),
            document.currency.strip().upper(),
            format(document.total.normalize(), "f"),
        )
    encoded = json.dumps(signature, ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _low_confidence_findings(
    document: FinancialDocument,
) -> list[ValidationFinding]:
    low_fields = sorted(
        field
        for field, confidence in document.field_confidence.items()
        if confidence < LOW_CONFIDENCE_THRESHOLD
    )
    if not low_fields:
        return []
    return [
        _warning(
            "primary_extraction_confidence_low",
            "field_confidence",
            "Primary extraction confidence is below 0.80 for: "
            + ", ".join(low_fields)
            + ".",
        )
    ]


def _normalize_identifier(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _missing(field: str, message: str) -> ValidationFinding:
    return _error(f"{field}_missing", field, message)


def _error(code: str, field: str, message: str) -> ValidationFinding:
    return ValidationFinding(code=code, field=field, severity="error", message=message)


def _warning(code: str, field: str, message: str) -> ValidationFinding:
    return ValidationFinding(code=code, field=field, severity="warning", message=message)
