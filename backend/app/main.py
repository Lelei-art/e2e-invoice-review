from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.auth import SESSION_COOKIE, is_valid_session
from backend.app.auth import router as auth_router
from backend.app.config import get_settings
from backend.app.routes import router

app = FastAPI(title="Apex Facilities Financial Document Review API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["content-type"],
)
app.include_router(router)
app.include_router(auth_router)


@app.middleware("http")
async def require_shared_password(request, call_next):
    settings = get_settings()
    path = request.url.path
    protected = path.startswith("/api/") and not path.startswith("/api/auth/")
    protected = protected or path in {"/docs", "/redoc", "/openapi.json"}
    if (
        settings.access_enabled
        and protected
        and not is_valid_session(request.cookies.get(SESSION_COOKIE), settings)
    ):
        return JSONResponse(
            status_code=401,
            content={"detail": "Sign in with the shared password to continue."},
        )
    return await call_next(request)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


settings = get_settings()
frontend_dist = settings.frontend_dist_dir or (
    Path(__file__).resolve().parents[2] / "frontend" / "dist"
)
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
