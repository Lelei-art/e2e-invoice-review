import argparse
import asyncio
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.pipeline.classification import classify_document  # noqa: E402
from backend.app.providers.azure_openai import MODEL_NAME  # noqa: E402

DEFAULT_DOCUMENT = (
    REPOSITORY_ROOT / "samples" / "generated" / "13-nl-fuel-receipt.png"
)


async def _classify(document_path: Path) -> None:
    result = await classify_document(document_path)
    print(f"Model: {MODEL_NAME}")
    print(f"Document: {document_path}")
    print("Classification:")
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify a PDF or image as an invoice, receipt, or other."
    )
    parser.add_argument(
        "document",
        nargs="?",
        type=Path,
        default=DEFAULT_DOCUMENT,
        help="PDF, PNG, or JPEG file (defaults to the fictional receipt sample)",
    )
    args = parser.parse_args()
    asyncio.run(_classify(args.document))


if __name__ == "__main__":
    main()
