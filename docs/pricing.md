# Pricing

The repository's current Azure OpenAI-compatible provider is configured to request
`grok-4.6`. Earlier GPT deployment estimates do not apply to this model and must
not be used for budgeting. Check the model's current Azure AI Foundry offer,
region, deployment type, and actual Azure Cost Management data before estimating
usage. This repository does not record a verified price for the configured model.

## What incurs provider usage

| Command or operation | Provider calls |
| --- | --- |
| `playground.map_document` | One Azure Document Intelligence analysis |
| `playground.classify_document` | One Azure OpenAI-compatible model request |
| `AzureOpenAIService.analyze_invoice()` or `.analyze_receipt()` | One Document Intelligence analysis and one model request |
| `backend/test.py` | One connection-check request and, when a question is entered, one additional model request |
| `playground.test_azure_openai` | One model request |

Document Intelligence usage is subject to the resource's tier, page limits,
region, and current pricing. Model requests are billed according to the
configured model offer and token usage. Each run can incur charges; no committed
corpus evaluator or web application is present on this branch.

For current rates, consult the [Azure Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices), the [Document Intelligence billing documentation](https://learn.microsoft.com/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0#billing), and the deployment's Azure Cost Management data.
