import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.services.document_intelligence_service import (  # noqa: E402
    DocumentIntelligenceService,
)

DEFAULT_RECEIPT = REPOSITORY_ROOT / "samples" / "generated" / "13-nl-fuel-receipt.png"


def analyze_receipt(document_path: Path = DEFAULT_RECEIPT) -> dict[str, object]:
    service = DocumentIntelligenceService()
    try:
        return service.analyze_receipt(document_path).as_dict()
    finally:
        service.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze a receipt with Azure Document Intelligence and print its result."
    )
    parser.add_argument(
        "document",
        nargs="?",
        type=Path,
        default=DEFAULT_RECEIPT,
        help=f"Receipt PDF or image to analyze (default: {DEFAULT_RECEIPT})",
    )
    args = parser.parse_args()

    result = analyze_receipt(args.document)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
