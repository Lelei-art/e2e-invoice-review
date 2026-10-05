import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

try:
    from backend.app.providers.azure_document_intelligence import (
        map_invoice_result,
        map_receipt_result,
    )
    from backend.app.services.document_intelligence_service import (
        DocumentIntelligenceService,
    )
except ModuleNotFoundError:  # pragma: no cover - only used when project deps are absent
    raise SystemExit(
        "Install the backend project environment first, then rerun with "
        "'uv run --project backend --locked --no-sync python -m playground.map_document'."
    ) from None

DEFAULT_RECEIPT = REPOSITORY_ROOT / "samples" / "generated" / "13-nl-fuel-receipt.png"
DEFAULT_INVOICE = REPOSITORY_ROOT / "samples" / "generated" / "01-en-happy-classic.pdf"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze a sample document and print its normalized Pydantic model."
    )
    parser.add_argument(
        "--type",
        choices=("invoice", "receipt"),
        default="receipt",
        help="Document Intelligence model to use (default: receipt)",
    )
    parser.add_argument(
        "document",
        nargs="?",
        type=Path,
        help="PDF or image to analyze (defaults to the fictional receipt sample)",
    )
    args = parser.parse_args()
    document_path = args.document or (
        DEFAULT_INVOICE if args.type == "invoice" else DEFAULT_RECEIPT
    )

    service = DocumentIntelligenceService()
    try:
        if args.type == "invoice":
            result = map_invoice_result(service.analyze_invoice(document_path))
        else:
            result = map_receipt_result(service.analyze_receipt(document_path))
    finally:
        service.close()

    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
