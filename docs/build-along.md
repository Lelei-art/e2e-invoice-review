# Build-along guide

The complete guided build lives at <https://learn.datalumina.com/docs/invoice-review>. This local guide records the first checkpoint represented by the `main` branch.

## Starter outcome

The repository installs reproducibly and includes the business brief, provider examples, Pydantic schemas, CLI playground commands, and fictional source documents. It does not yet include a runnable FastAPI application or React interface.

## Why this boundary exists

The starter removes the completed workflow while preserving every prerequisite needed to build it. You begin with the user, the source documents, and explicit service boundaries instead of reverse-engineering a finished application.

## Commands

```bash
uv sync --project backend --locked

pnpm --dir frontend install --frozen-lockfile
```

Copy the environment templates only when running the provider probes:

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

## Important locations

- `docs/client-brief.md`: the recurring finance problem and definition of done
- `docs/architecture.md`: the intended boundaries and data flow
- `samples/`: the fictional evaluation corpus and manifest
- `backend/app/providers/`: Azure provider adapters
- `backend/app/schemas/`: normalized invoice, receipt, and classification models
- `playground/`: local command-line probes for configured Azure providers

## What you should observe

- Both locked dependency installs complete successfully.
- The playground `--help` commands work without sending requests to Azure.
- No local web server is available at this checkpoint.

## Checkpoint

- [ ] Locked backend and frontend installs succeed.
- [ ] Backend lint passes.
- [ ] Frontend type-check, lint, and production build pass.
- [ ] `playground.map_document --help` and `playground.classify_document --help` display their options.
- [ ] No Azure request occurs until a provider command is run without `--help`.

Continue with the [online tutorial](https://learn.datalumina.com/docs/invoice-review).

## Document Intelligence receipt probe

### Outcome

Run the playground example to send the fictional Dutch fuel receipt to Azure Document Intelligence's `prebuilt-receipt` model. The reusable `DocumentIntelligenceService` lives in the backend; the sample selection and JSON output live in `playground/analyze_invoice.py`. The default input is `samples/generated/13-nl-fuel-receipt.png`; pass another PDF or image path to analyze a different receipt.

### Why

This small provider check confirms the configured Azure endpoint and key work before building the complete invoice-review workflow. Keeping the Azure client lifecycle and receipt-analysis operation in a reusable class separates the provider surface from the example script. The script prints the SDK's complete `AnalyzeResult` data model as formatted JSON so extracted fields and confidence values are easy to inspect.

### Commands

```bash
uv run --project backend --locked --no-sync python -m playground.analyze_invoice
```

To analyze a different document, provide its path:

```bash
uv run --project backend --locked --no-sync python -m playground.analyze_invoice samples/generated/13-nl-fuel-receipt.png
```

The script also exposes a function for an interactive Python session. Start the session in the repository root with the backend environment:

```bash
uv run --project backend --locked --no-sync python
```

Then import and call it:

```python
from playground.analyze_invoice import analyze_receipt

result = analyze_receipt()
print(result["content"])
```

Pass a `Path` to analyze a different document:

```python
from pathlib import Path

result = analyze_receipt(Path("samples/generated/13-nl-fuel-receipt.png"))
```

### What you should observe

The command prints the complete Azure `AnalyzeResult` JSON to the terminal. The result uses the `prebuilt-receipt` model and includes the extracted receipt text, fields, and confidence values. Each run sends one document-analysis request to Azure.

### Checkpoint

- [ ] The service reads the Document Intelligence endpoint and key from `backend/.env`.
- [ ] The default sample receipt is analyzed with `prebuilt-receipt`.
- [ ] The full structured SDK result prints as JSON.

## Azure OpenAI connection probe

### Outcome

`AzureOpenAIService` analyzes invoice and receipt files with Document Intelligence and independently extracts their fields with the hardcoded `grok-4.6` model. It returns both results and a merged model: Document Intelligence values stay primary, missing fields can be filled from Grok, and conflicting values are listed for review. The service and adapters live in `backend/app/services/` and `backend/app/providers/`; the OpenAI SDK types stay in its provider adapter. Azure OpenAI endpoint and key are read from the configured backend environment.

### Why

The standalone smoke probe remains a prompt-only connection check. The document analysis methods demonstrate the intended two-provider flow for the same original file.

### Commands

From the repository root, run:

```bash
uv run --project backend --locked --no-sync python backend/test.py
```

The script first checks the connection, then prompts for a question. It reads `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` from `backend/.env`; the model name is hardcoded as `grok-4.6`. Each run sends two requests to Azure and may incur usage charges.

### What you should observe

After entering a question, the terminal prints Grok's response. The API key is never printed. Authentication, permission, quota, rate-limit, connection, and other API errors are reported without exposing credentials.

### Checkpoint

- [ ] The service uses the configured endpoint and `grok-4.6` model.
- [ ] The key value is not printed.
- [ ] The connection check succeeds and the terminal accepts a question.
- [ ] Grok's response is printed in the terminal.

The playground provides the same service with a custom prompt:

```bash
uv run --project backend --locked --no-sync python -m playground.test_azure_openai "Summarize what an invoice is in one sentence."
```

Or load a UTF-8 prompt from a text file:

```bash
uv run --project backend --locked --no-sync python -m playground.test_azure_openai --prompt-file path/to/prompt.txt
```

With no arguments, the playground sends the default connection-check prompt. Each invocation makes one live request and may incur usage charges.

Print the complete SDK response model as JSON along with the answer:

```bash
uv run --project backend --locked --no-sync python -m playground.test_azure_openai --dump
```

The dump is produced from the OpenAI SDK response's Pydantic `model_dump(mode="json")`; it contains response fields, not credentials.

Use the combined service to run Document Intelligence first, then independently extract typed invoice or receipt fields with Grok and fill only missing primary values:

```python
from pathlib import Path

from backend.app.services.azure_openai_service import AzureOpenAIService

service = AzureOpenAIService()
try:
    invoice = service.analyze_invoice(Path("samples/generated/01-en-happy-classic.pdf"))
    print(invoice.model_dump(mode="json"))  # Includes both extractions, merged values, sources and conflicts.

    receipt = service.analyze_receipt(Path("samples/generated/13-nl-fuel-receipt.png"))
    print(receipt.model_dump(mode="json"))
finally:
    service.close()
```

These methods send each original document to both providers. The returned Pydantic analysis includes Document Intelligence fields, Grok fields, merged fields, field provenance, and conflicts. Each document analysis makes one Document Intelligence request and one Grok request; the calls may incur usage charges.

## Pydantic document schemas

### Outcome

The application has separate provider-independent Pydantic models for invoices and receipts under `backend/app/schemas/`. The Azure adapter maps the `prebuilt-invoice` and `prebuilt-receipt` field names into those normalized models, preserving extracted field confidence and line-item and tax detail data.

### Why

The Azure response contains provider-specific field names and typed values. Mapping it once at the provider boundary lets application rules work with stable names, dates, and decimal amounts without depending on Azure SDK classes.

### Commands

From the repository root, analyze the default fictional receipt and print its normalized Pydantic model:

```bash
uv run --project backend --locked --no-sync python -m playground.map_document
```

Analyze a fictional invoice instead:

```bash
uv run --project backend --locked --no-sync python -m playground.map_document --type invoice samples/generated/01-en-happy-classic.pdf
```

To analyze another receipt, pass its path:

```bash
uv run --project backend --locked --no-sync python -m playground.map_document --type receipt samples/generated/13-nl-fuel-receipt.png
```

### What you should observe

The command makes one Azure analysis request and prints normalized JSON. Invoice amounts and receipt totals use `Decimal` in the Python models; dates and times use Python date/time types. Optional fields stay `null` when Document Intelligence does not return them, and per-field confidence is retained where available.

Microsoft's field references: [prebuilt invoice](https://learn.microsoft.com/azure/ai-services/document-intelligence/prebuilt/invoice?view=doc-intel-4.0.0) and [prebuilt receipt](https://learn.microsoft.com/azure/ai-services/document-intelligence/prebuilt/receipt?view=doc-intel-4.0.0).

### Checkpoint

- [ ] The invoice sample maps to `Invoice` with the invoice number, parties, amounts, tax and line items.
- [ ] The receipt sample maps to `Receipt` with merchant, transaction date, totals, tax details and items.
- [ ] The normalized schemas do not import Azure SDK types.

## Pydantic AI document classification

### Outcome

An initial pipeline step sends the original PDF or image to the configured `grok-4.6` model and returns a strict Pydantic classification: `invoice`, `receipt`, or `other`, with a short reason. Unsupported or uncertain documents are classified as `other`. This step does not extract financial fields or invoke Document Intelligence.

### Why

The classifier demonstrates Pydantic AI structured output using the existing Azure OpenAI-compatible endpoint and credentials. The provider adapter owns the SDK client and closes it after the request; the pipeline exposes only the provider-independent Pydantic result.

### Commands

From the repository root, classify the default fictional receipt:

```bash
uv run --project backend --locked --no-sync python -m playground.classify_document
```

Classify a fictional invoice or another local PDF, PNG, or JPEG:

```bash
uv run --project backend --locked --no-sync python -m playground.classify_document samples/generated/01-en-happy-classic.pdf
```

Each run sends one original document to Azure and may incur usage charges. No credentials are printed.

### What you should observe

The terminal prints the model name, selected document path, and a JSON object with `document_type` and `reason`.

### Checkpoint

- [ ] The sample receipt is classified as `receipt`.
- [ ] An invoice sample is classified as `invoice`.
- [ ] Unsupported or uncertain documents can be returned as `other`.
- [ ] The pipeline result is validated by `DocumentClassification`; no raw model text is used as classification.
