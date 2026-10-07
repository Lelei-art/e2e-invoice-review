from backend.app.invoices.validation import validate_document
from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.receipt.model import Receipt
from backend.app.schemas.validation import ValidationFinding


class DocumentValidationStep:
    """Apply local VAT and amount checks to normalized document data."""

    def run(self, *, document: Invoice | Receipt) -> list[ValidationFinding]:
        return validate_document(document)
