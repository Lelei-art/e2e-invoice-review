# API endpoints and document-processing pipeline

This guide documents the local FastAPI API used by the frontend. The API processes financial documents—both invoices and receipts—and stores review records locally.

## Run the application locally

From the repository root, start the API with the existing locked backend environment:

```powershell
uv run --project backend --locked --no-sync uvicorn backend.app.main:app --reload
```

The API is titled **Apex Facilities Financial Document Review API** in OpenAPI. It listens at `http://127.0.0.1:8000`; the frontend runs separately at `http://localhost:5173` and sends requests to `http://localhost:8000` by default. Set `VITE_API_BASE_URL` in the frontend environment to use a different API base URL. Azure provider settings must be configured in `backend/.env` for document processing; health, review-history, and API-description requests do not need Azure credentials.

Open `http://localhost:8000/docs` for interactive Swagger UI, `http://localhost:8000/redoc` for ReDoc, or `http://localhost:8000/openapi.json` for the OpenAPI document.

## Endpoints

| Method | Path | Purpose | Azure required? |
| --- | --- | --- | --- |
| `GET` | `/health` | Simple API liveness check | No |
| `POST` | `/api/documents` | Process one invoice or receipt and save a review | Yes |
| `POST` | `/api/documents/progress` | Process and save one document; stream progress and the saved review | Yes |
| `GET` | `/api/documents` | List saved reviews | No |
| `GET` | `/api/documents/{review_id}` | Get one saved review | No |
| `PATCH` | `/api/documents/{review_id}` | Edit review fields and/or the selected GL account | No |
| `POST` | `/api/documents/{review_id}/decision` | Approve or reject a review | No |
| `POST` | `/api/documents/{review_id}/correction-email` | Draft a supplier correction email | Yes |
| `DELETE` | `/api/documents/{review_id}` | Delete a saved review and its duplicate fingerprint | No |
| `GET` | `/openapi.json` | FastAPI-generated OpenAPI schema | No |
| `GET` | `/docs` | Swagger UI for the OpenAPI schema | No |
| `GET` | `/redoc` | ReDoc API reference for the OpenAPI schema | No |

There is no authentication or authorization middleware in this local development API. CORS allows `GET`, `POST`, `PATCH`, and `DELETE` requests from `http://localhost:5173` with the `content-type` header.

### `GET /health`

Returns `200 OK` with:

```json
{"status": "ok"}
```

This is a liveness response from the FastAPI process; it does not test Azure credentials, SQLite, or provider connectivity.

### `POST /api/documents`

This is the non-streaming upload endpoint. It processes the document, saves a review record, and returns that record as JSON. The path uses `/documents` because the API accepts invoices and receipts, not invoices alone.

**Request**

- Content type: `multipart/form-data`
- Required field: `file` (one PDF, PNG, or JPEG)
- Maximum file size: 4 MiB (4,194,304 bytes)
- Supported filename extensions: `.pdf`, `.png`, `.jpg`, `.jpeg`
- The file's initial bytes must match its extension: PDF `%PDF-`, PNG signature, or JPEG signature.

Example using a generated PDF from the repository root:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/documents" `
  -F "file=@samples/generated/01-en-happy-classic.pdf"
```

**Successful response**

Returns `200 OK` and a `DocumentReview` JSON object. The extracted pipeline result is nested under `result`:

```json
{
  "id": "review-uuid",
  "filename": "01-en-happy-classic.pdf",
  "status": "needs_review",
  "result": {
    "classification": {
      "document_type": "invoice",
      "reason": "The document contains an invoice number and a supplier payment request."
    },
    "document": {
      "document_type": "invoice",
      "source_model": "prebuilt-invoice",
      "invoice_number": "INV-1001",
      "invoice_date": "2026-01-12",
      "vendor_name": "Example Supplier B.V.",
      "vendor_vat_id": "NL123456789B01",
      "customer_name": "Apex Facilities B.V.",
      "customer_vat_id": "NL00449544B01",
      "currency": "EUR",
      "subtotal": "100.00",
      "total_tax": "21.00",
      "invoice_total": "121.00",
      "line_items": [],
      "tax_details": [],
      "field_confidence": {}
    },
    "general_ledger_accounts": [
      {
        "code": "6080",
        "name": "Utilities",
        "description": "Energy, water, and utility services."
      }
    ],
    "general_ledger_suggestion": {
      "account_code": "6080",
      "reason": "The document describes a utility expense."
    },
    "validation_findings": []
  },
  "selected_gl_account_code": null,
  "decision_reason": null,
  "created_at": "2026-01-12T10:30:00Z",
  "updated_at": "2026-01-12T10:30:00Z"
}
```

The example is abbreviated: `result` includes the complete fixed GL catalog, extracted document fields, and validation findings. Decimal values (such as monetary totals) are serialized as JSON strings. The same endpoint accepts receipts; classification routes them to the receipt extractor and receipt-specific rules. For a receipt, `result.document` uses receipt fields. If classification is `other`, `result.document` and `result.general_ledger_suggestion` are `null`.

The returned `id` is the review ID used by the history and delete endpoints. The saved record contains the review result and metadata, not the uploaded file bytes.

### `GET /api/documents` and `GET /api/documents/{review_id}`

List saved reviews, newest first:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/documents"
```

Get one saved review using the `id` returned by `POST /api/documents` or `POST /api/documents/progress`:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/documents/review-uuid"
```

Both requests return `DocumentReview` objects. A review ID that is not present returns `404 Not Found`.

### `DELETE /api/documents/{review_id}`

Delete a saved review and its associated invoice/receipt duplicate fingerprint:

```powershell
Invoke-RestMethod -Method Delete "http://127.0.0.1:8000/api/documents/review-uuid"
```

Success returns `204 No Content`; an unknown ID returns `404 Not Found`. Deleting also removes that review's duplicate-check entry, so the same financial document can be processed again without matching that deleted review.

### `PATCH /api/documents/{review_id}` and decision

Bill can correct extracted scalar fields and explicitly select a GL account by sending a `PATCH` request. The server validates the fields, reruns the local finance rules and duplicate check, marks edited fields as human-provided, and saves the updated review:

```json
{
  "fields": {
    "vendor_vat_id": "FR61954506077",
    "invoice_total": "121.00"
  },
  "selected_gl_account_code": "6020"
}
```

Only fields supported for that invoice/receipt type may be changed. A review can pass only when it has no `error` findings and a valid GL account is selected. Warnings remain visible but do not block approval. Updates to an approved or rejected review return `409 Conflict`.

Review status is `needs_review` while blocking findings remain or no GL account has been selected, `ready` when those requirements are satisfied, and `approved` or `rejected` after a final decision. Editing a saved review reruns deterministic finance checks and may move it between `needs_review` and `ready`. Approved and rejected reviews are locked.

To pass an eligible review:

```json
{"decision": "approved"}
```

To reject it, a reason is required:

```json
{"decision": "rejected", "reason": "The supplier sent a corrected invoice."}
```

Both decisions use `POST /api/documents/{review_id}/decision` and return the saved review. Decisions are final; a final review is locked from further edits or decisions.

### `POST /api/documents/{review_id}/correction-email`

When supplier-correctable findings are present, Bill can request a structured draft:

```json
{"recipient_email": "supplier@example.eu"}
```

The response contains `to`, `subject`, and `body`. This endpoint makes an on-demand Azure OpenAI call and drafts text only; it does not send email. The draft is based on the findings and extracted values and remains for Bill to review and copy.

### `POST /api/documents/progress`

This is the streaming endpoint currently used by the frontend. The multipart request and validation rules are the same as for `/api/documents`. The response is `200 OK` with content type `text/event-stream`; events use Server-Sent Events framing (`event:` and `data:` lines separated by a blank line).

For each stage reached, the API emits a `progress` event when it starts and another when it completes:

```text
event: progress
data: {"stage": "classification", "status": "started"}

event: progress
data: {"stage": "classification", "status": "completed"}
```

Stages are emitted in this order:

1. `classification`
2. `extraction`
3. `validation`
4. `general_ledger`

When processing succeeds, the stream ends with a `result` event whose `data` is the saved `DocumentReview` object. Its extracted pipeline result is under `result`:

```text
event: result
data: {"id":"review-uuid","filename":"13-nl-fuel-receipt.png","status":"needs_review","result":{"classification":{"document_type":"receipt","reason":"..."},"document":{...},"general_ledger_accounts":[...],"general_ledger_suggestion":{...},"validation_findings":[]},"selected_gl_account_code":null,"decision_reason":null,"created_at":"...","updated_at":"..."}
```

The frontend displays the nested `result` while the review ID can be used with the history endpoints. If classification returns `other`, processing stops after classification, but a review record is still saved and returned. Stages that were not run are not reported as completed.

If an exception occurs after streaming has begun, the HTTP status can no longer be changed. The API logs the underlying exception and emits an `error` event with a generic message:

```text
event: error
data: {"message":"Document processing failed. Check the API logs for details."}
```

The frontend reads this stream and updates its progress UI from these backend events; it does not use a timer to pretend that work has completed.

Example request:

```powershell
curl.exe -N -X POST "http://127.0.0.1:8000/api/documents/progress" `
  -F "file=@samples/generated/13-nl-fuel-receipt.png"
```

### Upload errors

The shared upload validation runs before either route starts provider processing:

| Status | Cause |
| --- | --- |
| `413 Payload Too Large` | File is larger than 4 MiB |
| `415 Unsupported Media Type` | Unsupported extension or content signature does not match the extension |
| `422 Unprocessable Content` | Empty upload; FastAPI also returns `422` when the required multipart `file` field is missing or malformed |
| `422 Unprocessable Content` | Invalid edit fields or a rejection without a reason |
| `404 Not Found` | A requested review ID does not exist |
| `409 Conflict` | An approval is blocked, a final review is locked, or a correction draft is not eligible |
| `502 Bad Gateway` | Azure OpenAI could not generate a correction email draft |

FastAPI returns these pre-processing errors as JSON, typically with a `detail` field. For the streaming endpoint, provider or pipeline failures after the response starts are sent as an SSE `error` event instead of a new HTTP error response.

## How one upload moves through the system

```text
Browser
  -> FastAPI route validates multipart upload
  -> request-scoped temporary file
  -> DocumentProcessingService
  -> DocumentProcessingPipeline
       1. classify original document
       2. extract using Document Intelligence and independent Azure OpenAI review
          (keep primary values; fill only missing fields and retain provenance/conflicts)
       3. apply deterministic validation rules
       4. suggest a GL account from the fixed catalog
  -> service saves the review and checks the duplicate fingerprint
  -> JSON review or SSE review result
  -> temporary file is removed
```

### 1. Upload validation and temporary storage

The browser sends the chosen file only after the user starts the review. The route validates the filename extension, reads at most one byte over the 4 MiB limit, rejects an empty file, and checks the file signature. It then writes the accepted bytes to a temporary directory so provider adapters can read a path. The temporary directory is removed when processing ends; the original upload is not stored as a document in the application database.

### 2. Classification

`DocumentClassificationStep` sends the original PDF or image to the configured Azure OpenAI model. It returns a strict structured classification of `invoice`, `receipt`, or `other`, plus a short reason. The model is asked to classify the visual document and not to extract its financial fields.

If the result is `other`, the pipeline stops. It does not run extraction, finance validation, GL suggestion, or invoice/receipt duplicate checks; a review record is still saved.

### 3. Financial-field extraction

For an invoice, `DocumentIntelligenceExtractionStep` uses Azure AI Document Intelligence's `prebuilt-invoice` model. For a receipt, it uses `prebuilt-receipt`. The independent Azure OpenAI extraction analyzes the same original file. Document Intelligence remains primary: deterministic merging fills only missing fields, keeps the primary value on conflict, and exposes field provenance and disagreements to Bill.

### 4. Deterministic VAT and policy checks

`DocumentValidationStep` calls local Python rules; this stage does not ask a model to decide whether a document is acceptable. Invoice rules check required parties and identifiers, EU VAT format/checksum, Apex Facilities' customer VAT ID, positive totals, date ordering, amount reconciliation, missing purchase-order warnings, and low extraction-confidence warnings. Receipt rules check required merchant/date/currency/total/VAT values, positive totals, subtotal/VAT/tip reconciliation, and low-confidence warnings. Reconciliation uses a EUR `0.01` tolerance.

These checks are local format/checksum and policy checks, not a live VIES VAT registration lookup.

### 5. GL suggestion

The GL categorizer receives normalized invoice or receipt fields, not the original document image. Azure OpenAI returns a structured suggestion constrained to the application's fixed Apex Facilities GL catalog. The API returns both the full fixed catalog and the suggested account. The suggestion is advisory; model output does not change the catalog or finance policy.

### 6. Duplicate history and final response

After the pipeline returns, `DocumentProcessingService` saves the review result and metadata in the local SQLite database at `backend/data/invoice-review.sqlite3`. It also stores a duplicate fingerprint for recognized invoices and receipts. The database stores the normalized review so it can be edited and reopened, but does not retain the uploaded file bytes. If a match was already present, the service appends a `duplicate_invoice` error or `possible_duplicate_receipt` warning to `validation_findings`.

The progress events currently report the pipeline stages above. Duplicate lookup/recording happens in the service after the `general_ledger` stage has completed, so it is reflected in the saved review result but does not have its own progress event. The review is then returned as JSON or sent as the final SSE `result` event.

## Result shape at a glance

The upload and review-history endpoints return a `DocumentReview` envelope with `id`, `filename`, `status`, `result`, the optional selected GL account and decision reason, and creation/update timestamps. The `id` identifies the saved review for later GET, PATCH, decision, and DELETE requests.

`DocumentProcessingResult` has these top-level fields:

| Field | Meaning |
| --- | --- |
| `classification` | `document_type` (`invoice`, `receipt`, or `other`) and model-provided `reason` |
| `document` | Normalized invoice or receipt object, or `null` when classification is `other` |
| `general_ledger_accounts` | Fixed list of valid account codes, names, and descriptions |
| `general_ledger_suggestion` | Structured suggested account code and reason, or `null` when not applicable |
| `validation_findings` | Array of `{code, field, severity, message}` findings; severity is `error` or `warning` |

The full field definitions are in the Pydantic schemas under `backend/app/schemas/`. The interactive OpenAPI page at `/docs` shows request and response definitions for the HTTP routes.

## Checking the evaluation manifest

Run the local deterministic-policy evaluation without Azure:

```powershell
uv run --project backend --locked --no-sync python backend/scripts/evaluate_corpus.py
```

It verifies the expected policy issue codes for all 13 manifest entries in corpus order, including the duplicate invoice. It does not exercise the classifier or extraction providers.

An optional live evaluation can exercise classification, extraction/merge, validation, GL suggestions, and expected normalized fields:

```powershell
uv run --project backend --locked --no-sync python backend/scripts/evaluate_corpus.py --live
```

The live run can make up to 52 Azure provider requests: 13 each for classification, Document Intelligence, independent Azure OpenAI extraction, and GL suggestions. It may incur charges. Review and duplicate history are isolated to a temporary SQLite file that is removed when the run completes; the normal local review database is not modified.

## Important current boundaries

- The API currently processes one upload per request; it is not a batch processor.
- Review history and explicit deletion are available, but there is no user authentication. The decision endpoint implements the local approval/rejection flow; correction-email generation drafts text only and does not send email.
- `GET /health` is a liveness check, not a dependency-readiness check.
- Do not expose this local development API to an untrusted network: it has no authentication and accepts uploaded financial documents.
- Azure calls can incur usage charges. Keep Azure credentials in the ignored `backend/.env`; do not put them in the frontend.

Related project context: [client brief](./client-brief.md), [architecture](./architecture.md), and [build-along guide](./build-along.md).
