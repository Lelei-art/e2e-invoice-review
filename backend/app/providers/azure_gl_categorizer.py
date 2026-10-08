import json

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from backend.app.accounting.catalog import GL_ACCOUNTS
from backend.app.providers.azure_openai import MODEL_NAME, AzureOpenAISettings
from backend.app.schemas.general_ledger import GeneralLedgerSuggestion
from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.receipt.model import Receipt


async def suggest_general_ledger(
    document: Invoice | Receipt,
) -> GeneralLedgerSuggestion:
    settings = AzureOpenAISettings()
    account_options = "\n".join(
        f"- {account.code}: {account.name} — {account.description}"
        for account in GL_ACCOUNTS
    )
    document_fields = json.dumps(
        document.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
    )

    async with AsyncOpenAI(
        base_url=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key.get_secret_value(),
    ) as client:
        model = OpenAIResponsesModel(
            MODEL_NAME,
            provider=OpenAIProvider(openai_client=client),
        )
        agent = Agent(
            model,
            output_type=GeneralLedgerSuggestion,
            instructions=(
                "Suggest the single best Apex Facilities general ledger account for this document. "
                "Use only the supplied normalized financial-document fields and choose "
                "exactly one code from "
                "the fixed catalog below. Do not create or modify account codes; the "
                "suggestion is advisory and does not determine approval. The document may "
                "be an invoice or receipt.\n"
                f"{account_options}"
            ),
        )
        result = await agent.run(
            "Choose the best ledger account for this normalized financial document:\n"
            f"{document_fields}"
        )
        return result.output
