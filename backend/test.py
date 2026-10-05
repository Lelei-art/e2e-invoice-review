import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.services.azure_openai_service import (  # noqa: E402
    AzureOpenAIRequestError,
    AzureOpenAIService,
)

CONNECTION_CHECK_PROMPT = "Reply with exactly: Azure OpenAI connection successful."


def main() -> None:
    service = AzureOpenAIService()
    try:
        print(f"Model: {service.model_name}")
        service.generate_response(CONNECTION_CHECK_PROMPT)
        print("Azure OpenAI connection successful.")

        question = input("\nAsk Grok a question: ").strip()
        if not question:
            print("No question entered; exiting without sending a question.")
            return

        answer = service.generate_response(question)
        print("\nGrok's answer:")
        print(answer)
    except AzureOpenAIRequestError as error:
        status = f" (HTTP {error.status_code})" if error.status_code else ""
        print(f"\n{error.category}{status}: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        service.close()


if __name__ == "__main__":
    main()
