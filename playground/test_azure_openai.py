import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.services.azure_openai_service import (  # noqa: E402
    AzureOpenAIRequestError,
    AzureOpenAIService,
)


# The question you want Grok to answer
PROMPT = "What is an invoice, and what information does it normally contain?"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send the sample prompt to Azure OpenAI and print its response."
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Also print the complete OpenAI response model as JSON",
    )
    args = parser.parse_args()

    print(f"Model: {AzureOpenAIService.model_name}")
    print("Sending request...\n")

    service = AzureOpenAIService()

    try:
        if args.dump:
            response, response_dump = service.generate_response_with_dump(PROMPT)
        else:
            response = service.generate_response(PROMPT)

        print("Grok's answer:")
        print(response)

        if args.dump:
            print("\nResponse model dump:")
            print(json.dumps(response_dump, ensure_ascii=False, indent=2))

    except AzureOpenAIRequestError as error:
        status = f" (HTTP {error.status_code})" if error.status_code else ""
        print(f"\n{error.category}{status}: {error}", file=sys.stderr)
        raise SystemExit(1) from None

    finally:
        service.close()


if __name__ == "__main__":
    main()
