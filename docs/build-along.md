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
- `playground/AGENTS.md`: import-path setup required for standalone playground scripts

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
The `DocumentClassificationStep` exposes an async `run()` method. Call it with `document_path=...`; it passes that named path to the provider, which reads the bytes and sends them to the model.

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

## Chained classification, extraction, and validation

### Outcome

`DocumentProcessingPipeline` classifies the original document, routes invoices and receipts to the matching Document Intelligence prebuilt model, and runs local validation on the normalized Pydantic model. As the final stage, invoices and receipts receive a structured Azure OpenAI general-ledger suggestion. The result includes the classification, normalized invoice/receipt data, optional ledger suggestion, and validation findings. Classification as `other` stops the chain before extraction.

### Why

Each step has one responsibility and passes a typed result to the next. Document Intelligence remains the source of extracted values. The final ledger categorizer receives normalized invoice or receipt fields only and returns a structured code from the fixed ten-account Apex Facilities catalog in `backend/app/accounting/catalog.py`; it cannot create new accounts or decide approval. VAT validation uses `python-stdnum` locally and does not query VIES. Invoice and receipt totals are compared with a EUR 0.01 tolerance; receipt tips are included in the reconciliation.

### Commands

From the repository root, process the default fictional receipt:

```bash
uv run --project backend --locked --no-sync python -m playground.process_document
```

Process an invoice instead:

```bash
uv run --project backend --locked --no-sync python -m playground.process_document samples/generated/01-en-happy-classic.pdf
```

Each run makes one classification request and, for invoices or receipts, one Document Intelligence request and one additional Azure OpenAI request for the ledger suggestion. Provider calls may incur usage charges.

### What you should observe

The terminal logs each pipeline stage to standard error: classification, Document Intelligence extraction, local validation, and the final ledger suggestion. The output JSON on standard output contains `classification`, `document`, `validation_findings`, `general_ledger_accounts` (the full fixed catalog), and `general_ledger_suggestion`; the existing playground command prints all fields from the pipeline result. Failures are logged with a traceback and then re-raised. A document classified as `other` has no extracted document and makes no Document Intelligence or ledger-suggestion request, but the available catalog is still included in the result. Invoice VAT and totals and receipt subtotal/VAT/total reconciliation produce explicit validation findings when invalid.

### Checkpoint

- [ ] Invoice classification selects `prebuilt-invoice` and returns an `Invoice`.
- [ ] Receipt classification selects `prebuilt-receipt` and returns a `Receipt`.
- [ ] Invoice VAT format/checksum and totals are checked offline.
- [ ] Receipt subtotal, VAT, optional tip, and total are reconciled locally.
- [ ] Invoice and receipt ledger suggestions use one of the ten fixed catalog codes.
- [ ] `other` documents have no ledger suggestion.
- [ ] `other` stops after classification.
- [ ] Stage progress is visible in the terminal without mixing log lines into the JSON output.

## Separate invoice and receipt policies with duplicate history

### Outcome

Invoice and receipt validation now have separate deterministic policies in `backend/app/invoices/validation.py`. Invoice checks cover required identities and fields, supplier/customer VAT (including Apex Facilities' expected customer VAT ID), positive totals, date order, EUR 0.01 reconciliation, missing-PO warnings, and low-confidence warnings. Receipt checks cover required merchant/date/currency/total/VAT, positive totals, subtotal/VAT/tip reconciliation, and low-confidence warnings.

The processing service records a SHA-256 fingerprint of each normalized document in the local SQLite database at `backend/data/invoice-review.sqlite3`. It does not store raw invoice fields or uploaded files; because the fingerprints are derived from business identifiers, treat the local database as sensitive. A repeated invoice with the same supplier VAT ID and invoice number adds a blocking error. A receipt matching merchant, transaction date, currency, and total adds a review warning because the same purchase amount can occur more than once. Unidentifiable documents are still recorded, but cannot be matched for duplicates. The database is ignored by Git.

### Why

Policies are ordinary Python and do not consult a model or a live VAT registry. Invoice and receipt requirements differ, so each type has its own validator. The repository handles SQLite reads and writes, while the service joins processing results with the duplicate-history check. Invoice duplicates block approval; receipt matches are advisory to reduce false positives.

### Commands

From the repository root, process the same fictional receipt twice:

```powershell
uv run --project backend --locked --no-sync python -m playground.process_document "samples/generated/13-nl-fuel-receipt.png"
uv run --project backend --locked --no-sync python -m playground.process_document "samples/generated/13-nl-fuel-receipt.png"
```

Use the same pattern with an invoice to exercise the blocking duplicate rule:

```powershell
uv run --project backend --locked --no-sync python -m playground.process_document "samples/generated/01-en-happy-classic.pdf"
```

Each command processes the document with the configured Azure providers and may incur usage charges. To reset local duplicate history, remove `backend/data/invoice-review.sqlite3` after confirming you no longer need it.

### What you should observe

The first successful processing run has no duplicate finding. Processing the same receipt again adds `possible_duplicate_receipt` with severity `warning`; repeating an invoice adds `duplicate_invoice` with severity `error`. Other policy violations appear as structured `validation_findings` in the JSON output. The local database contains fingerprints and timestamps, not extracted document fields.

### Checkpoint

- [ ] Invoices and receipts follow their separate required-field, reconciliation, and confidence rules.
- [ ] Missing purchase orders are invoice warnings; receipts do not require an invoice number, PO, or customer VAT.
- [ ] Invoice customer VAT is checked against Apex Facilities' fictional VAT ID.
- [ ] Reprocessing an invoice with the same supplier VAT ID and invoice number produces a blocking duplicate finding.
- [ ] Reprocessing a receipt with the same merchant, date, currency, and total produces a warning.
- [ ] Duplicate history is stored in the Git-ignored local SQLite database.

## FastAPI document-processing endpoint

### Outcome

`backend/app/main.py` creates the **Apex Facilities Financial Document Review API**. Both upload routes process one invoice or receipt and save a review record in local SQLite. The API lists/retrieves reviews, lets Bill edit extracted values and select a GL account, revalidates changes, records a guarded pass/approval or rejection with a required reason, generates unsent correction-email drafts, and deletes reviews with their duplicate fingerprints. Temporary upload bytes are removed after processing. See [API endpoints and document-processing pipeline](./api-and-pipeline.md) for the route contract and lifecycle.

### Why

The router handles HTTP input and status codes while orchestration, persistence, provider access, and pure finance rules stay in their own modules. The review ID links processing results to the history and decision endpoints. Checking file signatures as well as extensions prevents provider adapters from receiving misleading media types. Naming the resource `/documents` makes clear that both receipts and invoices are supported.

### Commands

From the repository root, start the API with the locked backend environment:

```powershell
uv run --project backend --locked --no-sync uvicorn backend.app.main:app --reload
```

In another terminal, check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Submit a generated receipt (Azure credentials in `backend/.env` must be configured):

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/documents" -F "file=@samples/generated/13-nl-fuel-receipt.png"
```

List saved reviews, then use an `id` from the response to fetch, edit, decide, or delete one:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/documents"
Invoke-RestMethod "http://127.0.0.1:8000/api/documents/<review-id>"
Invoke-RestMethod -Method Delete "http://127.0.0.1:8000/api/documents/<review-id>"
```

Use `http://127.0.0.1:8000/docs` to try the PATCH, decision, and correction-draft routes. Processing and correction drafting call configured Azure providers and may incur usage charges; the correction draft is never sent. Listing, retrieving, editing, deciding, and deleting saved reviews use local application logic and SQLite.

### What you should observe

The health endpoint returns `{"status":"ok"}`. A supported upload returns a review ID, status, and nested pipeline result. An edit saves human-provided field values and refreshed validation findings. Approval is rejected unless all blocking findings are resolved and Bill selected a GL account; rejection requires a reason. Final reviews are locked. DELETE returns HTTP 204 and clears the linked duplicate fingerprint. Unsupported file types return HTTP 415, empty files return HTTP 422, and uploads larger than 4 MB return HTTP 413. Uploaded bytes are not retained after processing.

### Checkpoint

- [ ] `GET /health` returns a successful status without requiring Azure credentials.
- [ ] OpenAPI describes upload, review-list/detail, edit, decision, correction draft, and delete routes.
- [ ] The route rejects unsupported, empty, oversized, and signature-mismatched uploads before Azure calls.
- [ ] A valid PDF/PNG/JPEG is sent through classification, extraction, GL suggestion, validation, and duplicate-history logic.
- [ ] The upload response includes its saved review ID and the provider-independent result.
- [ ] History and review decisions work without Azure; deletion removes the review's duplicate fingerprint.

## Frontend welcome and pipeline launch

### Outcome

The React frontend provides upload, preview, live processing, a saved-review inbox, and a review workspace. Bill can check document values, billed items, the VAT breakdown, and readable comparisons when two readings disagree. Invoice extraction includes a separately shown remaining amount due when the document explicitly states one; the field stays blank rather than guessing from the invoice total. Editing a value or selecting an account and then choosing a decision saves the changes and reruns finance checks first. Passing is blocked if issues remain or no account is selected; rejection requires a reason. Final reviews lock, and deletion removes the review and its duplicate fingerprint.

### Why

The browser owns document selection and presentation, while all HTTP calls go through the typed client in `frontend/src/lib/api.ts`. The API remains the only path to classification, extraction, deterministic policy, duplicate history, decisions, and GL suggestion. The frontend does not contain provider credentials or finance policy.

### Commands

In the first terminal, from the repository root, start FastAPI:

```powershell
uv run --project backend --locked --no-sync uvicorn backend.app.main:app --reload
```

In a second terminal, start the frontend from its package directory so Corepack selects the pinned pnpm 11.3.0:

```powershell
Set-Location frontend
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open `http://localhost:5173`, choose a generated sample such as `samples/generated/13-nl-fuel-receipt.png`, and click **Start document review**. Use **Review inbox** to reopen the saved result. Check `http://localhost:8000/docs` for the API description. Processing calls Azure providers and may incur usage charges; correction-email drafting makes another call only when requested.

### What you should observe

Before selection, the drop zone invites file selection. The preview confirms the document before processing. Pipeline steps update from backend events. In the saved review, Bill can inspect details, billed items, VAT, and readable value comparisons, edit values, choose an account, and resolve validation issues. The pass action saves and rechecks pending edits before approval; rejection requires a reason and is also available for unsupported documents. Supplier email drafts are reviewed/copied manually, never sent.

### Checkpoint

- [ ] The welcome screen supports click-to-select and drag-and-drop.
- [ ] A selected PDF or image is previewed before processing.
- [ ] The user can choose a different file from the preview screen.
- [ ] Supported extensions and the 4 MB size limit are checked before sending.
- [ ] The user explicitly starts processing after choosing a document.
- [ ] The frontend posts multipart field `file` to the configured API base URL.
- [ ] Processing steps update from actual backend progress events in pipeline order.
- [ ] Processing failures and unsupported classifications are visible.
- [ ] History lists saved reviews and lets Bill reopen a review.
- [ ] Editing and saving reruns deterministic rules and marks changed values as human-provided.
- [ ] Pending edits are saved and rechecked before a decision; approval requires no blocking errors and a selected bookkeeping account.
- [ ] Rejection requires a reason, and the pass/reject confirmation actions record their decisions.
- [ ] Final decisions lock a review, and deletion clears its duplicate fingerprint.
- [ ] Correction email drafting does not send email.
- [ ] Successful results show document details, billed items, VAT breakdown, readable extraction differences, finance checks, and the suggested account.
- [ ] Invoice amount due is extracted only when explicitly shown; otherwise, the review field remains available for correction without inferring it from the invoice total.
- [ ] TypeScript, ESLint, and the production build pass without adding frontend dependencies.

## Check the sample evaluation manifest

### Outcome

Run the deterministic policy evaluator against all 13 fictional samples and their expected outcomes. The current local run passes all 13 samples, including VAT findings, reconciliation, and the duplicate-invoice case. This check does not call Azure.

### Why

The manifest defines the expected policy outcomes used to keep local business rules aligned with the example corpus. Running samples in manifest order also verifies the duplicate behavior without involving model variability or provider costs.

### Commands

From the repository root in PowerShell:

```powershell
uv run --project backend --locked --no-sync python backend/scripts/evaluate_corpus.py
```

To also exercise live classification, extraction, and GL suggestion against all 13 samples:

```powershell
uv run --project backend --locked --no-sync python backend/scripts/evaluate_corpus.py --live
```

The live mode may make up to 52 Azure provider requests and incur charges. Run it only when the Azure configuration is available and the usage is approved.

### What you should observe

Offline mode prints the expected and actual issue codes for each filename, then `Policy evaluation: 13/13 samples passed.` It reports that no Azure calls were made. Live mode additionally reports normalized-field mismatches and provider failures; a passing offline run does not imply the live extraction evaluation has passed.

### Checkpoint

- [ ] The offline evaluator passes all 13 manifest entries.
- [ ] Sample 10 is reported with `duplicate_invoice` after sample 03 has established its duplicate fingerprint.
- [ ] No Azure requests are made by the default command.
- [ ] Live evaluation is only run with approval for the potential provider usage.

## Start the backend and frontend together

### Outcome

Run `.\run-dev.ps1` from the repository root in Windows PowerShell to start FastAPI and Vite together. Use `bash run-dev.sh` on macOS/Linux or Git Bash.

### Why

The browser frontend needs the FastAPI backend while developing the upload flow. The short launcher runs both existing dev commands concurrently in one terminal session and does not install dependencies.

### Commands

Install dependencies first if needed, then from the repository root in Windows PowerShell:

```powershell
.\run-dev.ps1
```

If dependencies have not been installed, install the backend and frontend first using the commands in the Install section. Open `http://localhost:5173` for the frontend or `http://127.0.0.1:8000/docs` for the API. Press Ctrl+C in the launcher terminal to stop the session.

### What you should observe

Both processes write their logs to the terminal. Vite serves the welcome screen on port 5173, and FastAPI serves `/health` and `/docs` on port 8000. Document processing still calls Azure and may incur usage charges.

### Checkpoint

- [ ] The Windows launcher can be invoked as `.\run-dev.ps1` from the repository root.
- [ ] Both existing development servers start without dependency installation.
- [ ] Their logs are visible in the same terminal session.
- [ ] Ctrl+C ends the launcher session.

## Deploy one protected container to Azure

### Outcome

The complete React application and FastAPI API run together in `ca-invoice-review` in the existing `rg-invoice-review` resource group. Its existing Document Intelligence and Foundry resources are reused. A shared password protects the review UI and API; SQLite review history persists on the `invoice-review-data` Azure Files share. Azure Container Apps provides the public HTTPS endpoint.

### Why

The built frontend uses same-origin API requests, so the deployment needs one public app endpoint rather than separate frontend and API services. Azure Files keeps the SQLite database outside the replaceable container. Its SMB mount requires SQLite's `unix-dotfile` VFS in this deployment; the default POSIX-lock VFS fails with `database is locked`. This setting is explicit and is only appropriate while the app remains a single replica using the same VFS for every connection. The app password and session-signing key are Container App secrets; the Azure provider keys are also injected as secrets and never added to the image or repository.

### Commands

The repository-root `Dockerfile` builds the frontend and installs the locked backend dependencies. The `.dockerignore` excludes local environment files, databases, and dependency/build directories. Build locally before provisioning:

```powershell
Set-Location frontend
corepack pnpm install --frozen-lockfile
corepack pnpm build
Set-Location ..
uv run --project backend --locked --no-sync ruff check backend/app
```

The deployed hosting resources reuse the existing resource group: ACR `acrinvrvw261008` and storage account `stinvrvw261008` are in East US; the Container Apps environment `cae-invoice-review-e2` and app `ca-invoice-review` are in East US 2. West Europe did not accept new hosting resources, and East US had no Container Apps capacity. The existing Foundry and Document Intelligence resources were not changed. Check the active subscription and resources before making any further deployment changes:

```powershell
az account show
az group show --name rg-invoice-review
az resource list --resource-group rg-invoice-review --output table
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.ContainerRegistry --wait
az provider register --namespace Microsoft.OperationalInsights --wait
```

The initial image was `acrinvrvw261008.azurecr.io/invoice-review:20261008-1153`. The SQLite-on-Azure-Files fix was built as `acrinvrvw261008.azurecr.io/invoice-review:20261008-094022-dotfile` and deployed by updating the existing app. For a later code update, generate a fresh tag rather than overwriting either deployed image:

```powershell
$tag = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss') + '-dotfile'
az acr build --registry acrinvrvw261008 --resource-group rg-invoice-review --image "invoice-review:$tag" .
az containerapp update --resource-group rg-invoice-review --name ca-invoice-review --image "acrinvrvw261008.azurecr.io/invoice-review:$tag" --set-env-vars SQLITE_VFS=unix-dotfile
```

The app already has the `invoice-review-data` Azure Files share mounted at `/app/backend/data`, public HTTPS ingress on port `8000`, one minimum/maximum replica, and Azure Monitor diagnostics. Do not create another registry, share, environment, or app. When configuring a fresh local development environment, leave `SQLITE_VFS` unset; only the Linux Azure Files deployment uses `unix-dotfile`. Keep the app at one replica and one Uvicorn process. Configure:

- `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` and `AZURE_OPENAI_ENDPOINT` as endpoint environment variables.
- `AZURE_DOCUMENT_INTELLIGENCE_KEY`, `AZURE_OPENAI_API_KEY`, `APP_ACCESS_PASSWORD`, and `APP_SESSION_SECRET` as Container App secrets, referenced by environment variables.
- `FRONTEND_DIST_DIR=/app/frontend/dist`.
- External ingress on port `8000`; Azure provides HTTPS.
- An `ALLOWED_ORIGIN` is not needed for the combined same-origin frontend/API.

Use the existing provider endpoint/key values from the ignored local `backend/.env`. Generate a new strong shared password and session secret for the hosted app; do not echo, commit, or pass secret values as build arguments. Obtain the final URL from `az containerapp show` after provisioning.

### What you should observe

`GET /health` returns `{"status":"ok"}`. The deployed HTTPS URL is `https://ca-invoice-review.happyplant-4cc89b4a.eastus2.azurecontainerapps.io/`. The active revision runs the `20261008-094022-dotfile` image with `SQLITE_VFS=unix-dotfile`, one replica, and the existing Azure Files mount. The UI returns HTTP 200; anonymous history access returns 401; password sign-in succeeds; and authenticated history access returns HTTP 200.

For the manual end-to-end walkthrough, sign in at the deployed URL, upload the fictional `samples/generated/01-en-happy-classic.pdf`, and select **Start document review**. The result classified it as an invoice, extracted the parties and EUR 100.00 subtotal + EUR 21.00 VAT = EUR 121.00 total, completed validation, and suggested GL account 6090. It correctly remained **Needs review** because primary extraction confidence for the supplier name was below 0.80; there were no blocking errors. Navigating to the Review inbox showed the saved review, confirming persistence in the mounted database. The app does not retain the original upload. This walkthrough made paid Azure AI requests; do not repeat it unless another processing check is intended.

The ACR Basic tier, storage, Container Apps environment, and logging may incur charges. Live document review also makes paid Azure AI requests. The shared password grants anyone who receives it access to the demo, so use fictional documents only and rotate it if shared beyond the intended audience.

### Checkpoint

- [ ] The existing AI resources remain in place; only missing hosting resources are added to `rg-invoice-review`.
- [ ] Azure hosting providers are registered and the container build succeeds.
- [ ] The Container App has public HTTPS ingress, one replica, the Azure Files data mount, and `SQLITE_VFS=unix-dotfile`.
- [ ] `/health` is healthy; the sign-in screen is public, but review endpoints reject unauthenticated requests.
- [ ] Sign-in succeeds with the shared password; the authenticated history endpoint initializes and reads the mounted SQLite database.
- [x] The fictional `samples/generated/01-en-happy-classic.pdf` completed classification, extraction, validation, GL suggestion, and persisted in review history; the low-confidence warning leaves it for human review.
- [ ] Review history remains after a new container revision starts.
