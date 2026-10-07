# Playground import setup

Playground scripts must work both as files and as modules. Direct execution puts
`playground/`, not the repository root, on `sys.path`, so add this bootstrap
before importing `backend` modules:

```python
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))
```

Keep standard-library imports above the bootstrap. Put project imports below it
and mark those imports with `# noqa: E402`; they intentionally follow the
`sys.path` setup, so Ruff's normal import-order rule does not apply.

From inside `playground/`, run a script with the backend environment like this:

```powershell
uv run --project ..\backend --locked --no-sync python .\classify_document.py
```

From the repository root, module execution also works:

```powershell
uv run --project backend --locked --no-sync python -m playground.classify_document
```
