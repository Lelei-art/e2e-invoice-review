# Invoice Review frontend

The React app lets Bill upload and preview a document, then follows real backend progress events. Its saved-review inbox supports editing extracted values, rerunning deterministic checks, selecting a GL account, passing or rejecting the document, and drafting an unsent supplier-correction email.

## Run locally

From the repository root on Windows, start both development servers together in PowerShell:

```powershell
.\run-dev.ps1
```

On macOS/Linux or Git Bash, use `bash run-dev.sh`. To start the servers separately, backend:

```bash
uv run --project backend --locked --no-sync uvicorn backend.app.main:app --reload
```

Frontend (from the repository root):

```bash
cd frontend
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open <http://localhost:5173>. Choose a PDF, PNG, or JPEG up to 4 MB, then click **Start document review**. The browser sends multipart field `file` to `POST http://localhost:8000/api/documents/progress`; the API streams real pipeline events and then the persisted review. Use **Review inbox** to reopen it. `POST /api/documents` remains available for non-streaming clients. Azure processing and correction-draft requests may incur charges; the app never sends email.

`VITE_API_BASE_URL` defaults to `http://localhost:8000`. To use another backend URL, set it in a local `frontend/.env` file based on `.env.example`.
