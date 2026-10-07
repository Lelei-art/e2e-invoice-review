import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from backend.app.accounting.catalog import get_gl_account
from backend.app.pipeline.classification import DocumentClassificationStep
from backend.app.pipeline.extraction import DocumentIntelligenceExtractionStep
from backend.app.pipeline.general_ledger import GeneralLedgerSuggestionStep
from backend.app.pipeline.validation import DocumentValidationStep
from backend.app.schemas.pipeline import DocumentProcessingResult

logger = logging.getLogger(__name__)
PipelineStage = Literal["classification", "extraction", "validation", "general_ledger"]
PipelineStageStatus = Literal["started", "completed"]
PipelineProgressCallback = Callable[[PipelineStage, PipelineStageStatus], None]


def _report_progress(
    callback: PipelineProgressCallback | None,
    stage: PipelineStage,
    status: PipelineStageStatus,
) -> None:
    if callback is not None:
        callback(stage, status)


class DocumentProcessingPipeline:
    """Run classification, provider-specific extraction, then local validation."""

    def __init__(self) -> None:
        self._classification_step = DocumentClassificationStep()
        self._extraction_step = DocumentIntelligenceExtractionStep()
        self._general_ledger_step = GeneralLedgerSuggestionStep()
        self._validation_step = DocumentValidationStep()

    async def run(
        self,
        *,
        document_path: Path,
        progress_callback: PipelineProgressCallback | None = None,
    ) -> DocumentProcessingResult:
        logger.info("Starting document pipeline for %s", document_path)
        try:
            _report_progress(progress_callback, "classification", "started")
            logger.info("Classifying document")
            classification = await self._classification_step.run(
                document_path=document_path
            )
            _report_progress(progress_callback, "classification", "completed")
            logger.info(
                "Classification complete: type=%s",
                classification.document_type,
            )
            if classification.document_type == "other":
                logger.info("Stopping pipeline: document type is unsupported")
                return DocumentProcessingResult(classification=classification)

            _report_progress(progress_callback, "extraction", "started")
            logger.info(
                "Extracting %s fields with Document Intelligence",
                classification.document_type,
            )
            document = await asyncio.to_thread(
                self._extraction_step.run,
                document_path=document_path,
                document_type=classification.document_type,
            )
            _report_progress(progress_callback, "extraction", "completed")
            logger.info("Document extraction complete")

            _report_progress(progress_callback, "validation", "started")
            logger.info("Validating extracted document")
            findings = self._validation_step.run(document=document)
            _report_progress(progress_callback, "validation", "completed")
            logger.info(
                "Validation complete: %d finding(s)",
                len(findings),
            )

            _report_progress(progress_callback, "general_ledger", "started")
            logger.info(
                "Suggesting a general ledger account for %s",
                classification.document_type,
            )
            general_ledger_suggestion = await self._general_ledger_step.run(
                document=document
            )
            _report_progress(progress_callback, "general_ledger", "completed")
            account = get_gl_account(general_ledger_suggestion.account_code)
            logger.info(
                "General ledger suggestion complete: %s %s",
                account.code,
                account.name,
            )

            logger.info("Document pipeline complete")
            return DocumentProcessingResult(
                classification=classification,
                document=document,
                general_ledger_suggestion=general_ledger_suggestion,
                validation_findings=findings,
            )
        except Exception:
            logger.exception("Document pipeline failed for %s", document_path)
            raise
