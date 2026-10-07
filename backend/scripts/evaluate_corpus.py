import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.invoices.validation import duplicate_finding, validate_document  # noqa: E402
from backend.app.repository import DocumentRepository  # noqa: E402
from backend.app.schemas.invoice.model import Invoice  # noqa: E402
from backend.app.schemas.pipeline import DocumentProcessingResult  # noqa: E402
from backend.app.schemas.receipt.model import Receipt  # noqa: E402
from backend.app.service import DocumentProcessingService  # noqa: E402

MANIFEST_PATH = REPOSITORY_ROOT / "samples" / "manifest.json"
SAMPLE_DIRECTORY = REPOSITORY_ROOT / "samples" / "generated"
RECEIPT_FIELD_MAP = {
    "vendor_name": "merchant_name",
    "invoice_date": "transaction_date",
    "invoice_total": "total",
}


def _expected_document(sample: dict[str, Any]) -> Invoice | Receipt:
    expected = sample["expected"]
    if sample["document_type"] == "invoice":
        values = {key: value for key, value in expected.items() if key != "document_type"}
        return Invoice.model_validate(values)
    values = {
        RECEIPT_FIELD_MAP.get(key, key): value
        for key, value in expected.items()
        if key
        in {
            "currency",
            "subtotal",
            "total_tax",
            "vendor_name",
            "invoice_date",
            "invoice_total",
        }
    }
    return Receipt.model_validate(values)


def evaluate_policy() -> bool:
    samples = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="invoice-review-eval-") as directory:
        repository = DocumentRepository(Path(directory) / "evaluation.sqlite3")
        failures = 0
        for sample in samples:
            document = _expected_document(sample)
            findings = validate_document(document)
            if repository.record_processed_document(document):
                findings.append(duplicate_finding(document))
            expected_codes = sorted(sample["expected_issue_codes"])
            actual_codes = sorted(finding.code for finding in findings)
            passed = actual_codes == expected_codes
            print(
                f"{'PASS' if passed else 'FAIL'} {sample['filename']}: "
                f"expected={expected_codes} actual={actual_codes}"
            )
            failures += not passed
    print(f"Policy evaluation: {len(samples) - failures}/{len(samples)} samples passed.")
    return failures == 0


def _compare_live_result(
    sample: dict[str, Any],
    result: DocumentProcessingResult,
) -> list[str]:
    errors: list[str] = []
    if result.classification.document_type != sample["document_type"]:
        errors.append(
            f"classification expected {sample['document_type']!r}, "
            f"got {result.classification.document_type!r}"
        )
    expected = sample["expected"]
    document = result.document
    if sample["document_type"] == "other" or document is None:
        errors.append("expected an extracted invoice or receipt")
    else:
        for expected_field, expected_value in expected.items():
            if expected_field == "document_type":
                continue
            field = (
                RECEIPT_FIELD_MAP.get(expected_field, expected_field)
                if document.document_type == "receipt"
                else expected_field
            )
            if not hasattr(document, field):
                if expected_value is not None:
                    errors.append(f"{expected_field}: field is not available")
                continue
            actual_value = document.model_dump(mode="json").get(field)
            if actual_value != expected_value:
                errors.append(
                    f"{expected_field}: expected {expected_value!r}, got {actual_value!r}"
                )
    expected_codes = sorted(sample["expected_issue_codes"])
    actual_codes = sorted(finding.code for finding in result.validation_findings)
    if actual_codes != expected_codes:
        errors.append(
            f"issue codes expected {expected_codes!r}, got {actual_codes!r}"
        )
    return errors


async def evaluate_live() -> bool:
    samples = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures = 0
    with tempfile.TemporaryDirectory(prefix="invoice-review-live-eval-") as directory:
        service = DocumentProcessingService(
            repository=DocumentRepository(Path(directory) / "evaluation.sqlite3")
        )
        for sample in samples:
            path = SAMPLE_DIRECTORY / sample["filename"]
            review = await service.process_for_review(
                document_path=path,
                filename=sample["filename"],
            )
            errors = _compare_live_result(sample, review.result)
            print(
                f"{'PASS' if not errors else 'FAIL'} {sample['filename']}"
                + (f": {'; '.join(errors)}" if errors else "")
            )
            failures += bool(errors)
    print(f"Live corpus evaluation: {len(samples) - failures}/{len(samples)} samples passed.")
    return failures == 0


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check deterministic policies against manifest.json, "
            "optionally run live Azure evaluation."
        )
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Run all 13 sample documents through Azure. Expected maximum: "
            "52 provider requests (13 classification, 13 Document Intelligence, "
            "13 independent extraction, 13 GL suggestions)."
        ),
    )
    args = parser.parse_args()

    policy_passed = evaluate_policy()
    if not policy_passed:
        return 1
    if args.live:
        return 0 if await evaluate_live() else 1
    print("No Azure calls made. Add --live to evaluate extraction and model behavior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
