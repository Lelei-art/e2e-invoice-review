import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.service import DocumentProcessingService  # noqa: E402

DEFAULT_DOCUMENT = REPOSITORY_ROOT / "samples" / "generated" / "13-nl-fuel-receipt.png"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def _process(document_path: Path) -> None:
    result = await DocumentProcessingService().run(document_path=document_path)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify, extract, and validate one invoice or receipt."
    )
    parser.add_argument(
        "document",
        nargs="?",
        type=Path,
        default=DEFAULT_DOCUMENT,
        help="PDF, PNG, or JPEG file (defaults to the fictional receipt sample)",
    )
    args = parser.parse_args()
    asyncio.run(_process(args.document))


if __name__ == "__main__":
    main()
