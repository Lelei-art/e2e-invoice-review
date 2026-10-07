import asyncio
import json
import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from backend.app.pipeline.document_processing import PipelineStage, PipelineStageStatus
from backend.app.providers.azure_openai import AzureOpenAIRequestError
from backend.app.schemas.review import (
    CorrectionEmailDraft,
    CorrectionEmailRequest,
    DocumentReview,
    ReviewDecisionRequest,
    ReviewUpdateRequest,
)
from backend.app.service import (
    DocumentProcessingService,
    ReviewConflictError,
    ReviewInputError,
    ReviewNotFoundError,
)

router = APIRouter(prefix="/api", tags=["documents"])
logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
@router.post(
    "/documents",
    response_model=DocumentReview,
    status_code=status.HTTP_200_OK,
)
async def process_document(
    file: Annotated[UploadFile, File(description="A PDF, PNG, or JPEG invoice or receipt.")],
) -> DocumentReview:
    suffix, content = await _read_valid_upload(file)
    with tempfile.TemporaryDirectory(prefix="invoice-review-") as temporary_directory:
        document_path = Path(temporary_directory) / f"document{suffix}"
        document_path.write_bytes(content)
        review = await DocumentProcessingService().process_for_review(
            document_path=document_path,
            filename=file.filename or document_path.name,
        )
    return review


@router.post("/documents/progress")
async def process_document_with_progress(
    file: Annotated[UploadFile, File(description="A PDF, PNG, or JPEG invoice or receipt.")],
) -> StreamingResponse:
    suffix, content = await _read_valid_upload(file)

    async def stream_events():
        with tempfile.TemporaryDirectory(prefix="invoice-review-") as temporary_directory:
            document_path = Path(temporary_directory) / f"document{suffix}"
            document_path.write_bytes(content)
            progress_events: asyncio.Queue[tuple[PipelineStage, PipelineStageStatus]] = (
                asyncio.Queue()
            )
            service = DocumentProcessingService()
            processing_task = asyncio.create_task(
                service.process_for_review(
                    document_path=document_path,
                    filename=file.filename or document_path.name,
                    progress_callback=lambda stage, stage_status: progress_events.put_nowait(
                        (stage, stage_status)
                    ),
                )
            )
            try:
                while True:
                    if processing_task.done():
                        while not progress_events.empty():
                            stage, stage_status = progress_events.get_nowait()
                            yield _server_sent_event(
                                "progress",
                                {"stage": stage, "status": stage_status},
                            )
                        if processing_task.cancelled():
                            return
                        error = processing_task.exception()
                        if error is not None:
                            logger.error(
                                "Streaming document processing failed",
                                exc_info=(type(error), error, error.__traceback__),
                            )
                            yield _server_sent_event(
                                "error",
                                {
                                    "message": (
                                        "Document processing failed. "
                                        "Check the API logs for details."
                                    )
                                },
                            )
                        else:
                            result = processing_task.result()
                            yield _server_sent_event(
                                "result",
                                result.model_dump(mode="json"),
                            )
                        return

                    try:
                        stage, stage_status = await asyncio.wait_for(
                            progress_events.get(),
                            timeout=0.25,
                        )
                    except TimeoutError:
                        continue
                    yield _server_sent_event(
                        "progress",
                        {"stage": stage, "status": stage_status},
                    )
            finally:
                if not processing_task.done():
                    try:
                        await processing_task
                    except Exception as error:
                        logger.error(
                            "Document processing failed after the progress stream closed",
                            exc_info=(type(error), error, error.__traceback__),
                        )

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/documents", response_model=list[DocumentReview])
def list_documents() -> list[DocumentReview]:
    return DocumentProcessingService().list_reviews()


@router.get("/documents/{review_id}", response_model=DocumentReview)
def get_document(review_id: str) -> DocumentReview:
    return _translate_review_errors(
        lambda: DocumentProcessingService().get_review(review_id)
    )


@router.patch("/documents/{review_id}", response_model=DocumentReview)
def update_document(
    review_id: str,
    update: ReviewUpdateRequest,
) -> DocumentReview:
    return _translate_review_errors(
        lambda: DocumentProcessingService().update_review(review_id, update)
    )


@router.post("/documents/{review_id}/decision", response_model=DocumentReview)
def decide_document(
    review_id: str,
    decision: ReviewDecisionRequest,
) -> DocumentReview:
    return _translate_review_errors(
        lambda: DocumentProcessingService().decide_review(review_id, decision)
    )


@router.post(
    "/documents/{review_id}/correction-email",
    response_model=CorrectionEmailDraft,
)
async def create_correction_email(
    review_id: str,
    request: CorrectionEmailRequest,
) -> CorrectionEmailDraft:
    service = DocumentProcessingService()
    try:
        return await asyncio.to_thread(
            _translate_review_errors,
            lambda: service.draft_correction_email(
                review_id, recipient_email=request.recipient_email
            ),
        )
    except AzureOpenAIRequestError as error:
        logger.error("Correction email generation failed: %s", error.category)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not draft the correction email: {error}",
        ) from error


@router.delete(
    "/documents/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document(review_id: str) -> None:
    _translate_review_errors(
        lambda: DocumentProcessingService().delete_review(review_id)
    )


def _translate_review_errors[T](operation: Callable[[], T]) -> T:
    try:
        return operation()
    except ReviewNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ReviewInputError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except ReviewConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error


async def _read_valid_upload(file: UploadFile) -> tuple[str, bytes]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a PDF, PNG, or JPEG document.",
        )

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded document is empty.",
        )
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="The maximum document size is 4 MB.",
        )
    if not _matches_file_signature(suffix, content):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The file content does not match its PDF, PNG, or JPEG extension.",
        )
    return suffix, content


def _matches_file_signature(suffix: str, content: bytes) -> bool:
    if suffix == ".pdf":
        return content.startswith(b"%PDF-")
    if suffix == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    return content.startswith(b"\xff\xd8\xff")


def _server_sent_event(event_name: str, payload: object) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
