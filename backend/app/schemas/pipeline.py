from pydantic import Field

from backend.app.accounting.catalog import GL_ACCOUNTS
from backend.app.schemas.classification import DocumentClassification
from backend.app.schemas.general_ledger import (
    GeneralLedgerAccount,
    GeneralLedgerSuggestion,
)
from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.receipt.model import Receipt
from backend.app.schemas.shared import StrictSchema
from backend.app.schemas.validation import ValidationFinding


class DocumentProcessingResult(StrictSchema):
    classification: DocumentClassification
    document: Invoice | Receipt | None = None
    general_ledger_accounts: list[GeneralLedgerAccount] = Field(
        default_factory=lambda: list(GL_ACCOUNTS)
    )
    general_ledger_suggestion: GeneralLedgerSuggestion | None = None
    validation_findings: list[ValidationFinding] = Field(default_factory=list)
