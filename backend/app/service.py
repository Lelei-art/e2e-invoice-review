from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from backend.app.accounting.catalog import GL_ACCOUNTS
from backend.app.invoices.validation import (
    duplicate_finding,
    supplier_fixable_findings,
    validate_document,
)
from backend.app.pipeline.document_processing import (
    DocumentProcessingPipeline,
    PipelineProgressCallback,
)
from backend.app.providers.azure_correction_email import draft_correction_email
from backend.app.repository import DocumentRepository
from backend.app.schemas.pipeline import DocumentProcessingResult
from backend.app.schemas.review import (
    CorrectionEmailDraft,
    DocumentReview,
    ReviewDecisionRequest,
    ReviewStatus,
    ReviewUpdateRequest,
)
from backend.app.schemas.shared import FieldProvenance

INVOICE_EDITABLE_FIELDS = {
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
}
RECEIPT_EDITABLE_FIELDS = {
    "merchant_name",
    "merchant_address",
    "transaction_time",
    "receipt_type",
    "country_region",
    "transaction_date",
    "currency",
    "subtotal",
    "total_tax",
    "tip",
    "total",
}


class ReviewNotFoundError(LookupError):
    pass


class ReviewConflictError(ValueError):
    pass


class ReviewInputError(ValueError):
    pass


class DocumentProcessingService:
    """Orchestrate document processing and the human review lifecycle."""

    def __init__(
        self,
        pipeline: DocumentProcessingPipeline | None = None,
        repository: DocumentRepository | None = None,
    ) -> None:
        self._pipeline = pipeline or DocumentProcessingPipeline()
        self._repository = repository or DocumentRepository()

    async def run(
        self,
        *,
        document_path: Path,
        progress_callback: PipelineProgressCallback | None = None,
    ) -> DocumentProcessingResult:
        result = await self._pipeline.run(
            document_path=document_path,
            progress_callback=progress_callback,
        )
        if result.document is not None:
            if self._repository.record_processed_document(result.document):
                result.validation_findings.append(duplicate_finding(result.document))
        return result

    async def process_for_review(
        self,
        *,
        document_path: Path,
        filename: str,
        progress_callback: PipelineProgressCallback | None = None,
    ) -> DocumentReview:
        result = await self._pipeline.run(
            document_path=document_path,
            progress_callback=progress_callback,
        )
        now = datetime.now(UTC)
        review = DocumentReview(
            id=str(uuid4()),
            filename=filename,
            status=self._status_for(result),
            result=result,
            created_at=now,
            updated_at=now,
        )
        duplicate = self._repository.create_review(review, result.document)
        if duplicate and result.document is not None:
            result.validation_findings.append(duplicate_finding(result.document))
            review.status = self._status_for(result)
            review.updated_at = datetime.now(UTC)
            self._repository.save_review(review, result.document)
        return review

    def list_reviews(self) -> list[DocumentReview]:
        return self._repository.list_reviews()

    def get_review(self, review_id: str) -> DocumentReview:
        review = self._repository.get_review(review_id)
        if review is None:
            raise ReviewNotFoundError(f"Review {review_id!r} was not found.")
        return review

    def update_review(
        self,
        review_id: str,
        update: ReviewUpdateRequest,
    ) -> DocumentReview:
        review = self.get_review(review_id)
        self._ensure_open(review)
        document = review.result.document
        if document is None:
            raise ReviewConflictError("A document classified as other cannot be edited.")

        allowed_fields = (
            INVOICE_EDITABLE_FIELDS
            if document.document_type == "invoice"
            else RECEIPT_EDITABLE_FIELDS
        )
        unknown_fields = set(update.fields) - allowed_fields
        if unknown_fields:
            raise ReviewInputError(
                "These fields are not editable: " + ", ".join(sorted(unknown_fields))
            )
        updated_data = document.model_dump(mode="python")
        updated_data.update(update.fields)
        try:
            updated_document = type(document).model_validate(updated_data)
        except (TypeError, ValueError) as error:
            raise ReviewInputError(f"Edited document fields are invalid: {error}") from error
        updated_document.field_provenance.update(
            {
                field: FieldProvenance(source="human")
                for field in update.fields
            }
        )

        findings = validate_document(updated_document)
        if self._repository.has_duplicate(
            updated_document,
            excluding_review_id=review.id,
        ):
            findings.append(duplicate_finding(updated_document))
        review.result.document = updated_document
        review.result.validation_findings = findings
        if "selected_gl_account_code" in update.model_fields_set:
            review.selected_gl_account_code = update.selected_gl_account_code
        review.status = self._status_for(
            review.result,
            selected_gl_account_code=review.selected_gl_account_code,
        )
        review.updated_at = datetime.now(UTC)
        self._repository.save_review(review, updated_document)
        return review

    def decide_review(
        self,
        review_id: str,
        request: ReviewDecisionRequest,
    ) -> DocumentReview:
        review = self.get_review(review_id)
        self._ensure_open(review)
        if request.decision == "rejected":
            reason = (request.reason or "").strip()
            if not reason:
                raise ReviewInputError("A reason is required when rejecting a document.")
            review.status = "rejected"
            review.decision_reason = reason
        else:
            if review.result.document is None:
                raise ReviewConflictError(
                    "A document classified as other cannot be approved."
                )
            if any(
                finding.severity == "error"
                for finding in review.result.validation_findings
            ):
                raise ReviewConflictError(
                    "Resolve all blocking finance findings before approving."
                )
            if review.selected_gl_account_code not in {
                account.code for account in GL_ACCOUNTS
            }:
                raise ReviewConflictError(
                    "Select a valid general-ledger account before approving."
                )
            review.status = "approved"
            review.decision_reason = None
        review.updated_at = datetime.now(UTC)
        self._repository.save_review(review, review.result.document)
        return review

    def delete_review(self, review_id: str) -> None:
        if not self._repository.delete_review(review_id):
            raise ReviewNotFoundError(f"Review {review_id!r} was not found.")

    def draft_correction_email(
        self,
        review_id: str,
        *,
        recipient_email: str,
    ) -> CorrectionEmailDraft:
        review = self.get_review(review_id)
        self._ensure_open(review)
        if "@" not in recipient_email or recipient_email.startswith("@"):
            raise ReviewInputError("Enter a valid supplier email address.")
        if not supplier_fixable_findings(review.result.validation_findings):
            raise ReviewConflictError(
                "There are no supplier-correctable findings for this document."
            )
        return draft_correction_email(review, recipient_email=recipient_email)

    def _ensure_open(self, review: DocumentReview) -> None:
        if review.status in {"approved", "rejected"}:
            raise ReviewConflictError(
                "This review is final and cannot be changed. Reprocess the document to start over."
            )

    def _status_for(
        self,
        result: DocumentProcessingResult,
        *,
        selected_gl_account_code: str | None = None,
    ) -> ReviewStatus:
        if result.document is None or any(
            finding.severity == "error" for finding in result.validation_findings
        ):
            return "needs_review"
        if selected_gl_account_code not in {account.code for account in GL_ACCOUNTS}:
            return "needs_review"
        return "ready"
