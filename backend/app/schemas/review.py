from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from backend.app.schemas.general_ledger import GLAccountCode
from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.pipeline import DocumentProcessingResult
from backend.app.schemas.receipt.model import Receipt
from backend.app.schemas.shared import StrictSchema

EditableDocument = Annotated[
    Invoice | Receipt,
    Field(discriminator="document_type"),
]
ReviewStatus = Literal["needs_review", "ready", "approved", "rejected"]


class DocumentReview(StrictSchema):
    id: str
    filename: str
    status: ReviewStatus
    result: DocumentProcessingResult
    selected_gl_account_code: GLAccountCode | None = None
    decision_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ReviewUpdateRequest(StrictSchema):
    fields: dict[str, str | int | float | None] = Field(default_factory=dict)
    selected_gl_account_code: GLAccountCode | None = None


class ReviewDecisionRequest(StrictSchema):
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=1000)


class CorrectionEmailRequest(StrictSchema):
    recipient_email: str = Field(min_length=3, max_length=254)


class CorrectionEmailDraft(StrictSchema):
    to: str
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
