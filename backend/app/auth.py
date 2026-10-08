import base64
import hashlib
import hmac
import time

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from backend.app.config import Settings, get_settings

router = APIRouter(prefix="/api/auth", tags=["authentication"])
SESSION_COOKIE = "invoice_review_session"
SESSION_LIFETIME_SECONDS = 12 * 60 * 60


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    password: str = Field(min_length=1, max_length=1024)


class SessionStatus(BaseModel):
    authenticated: bool


@router.get("/session", response_model=SessionStatus)
def session_status(request: Request) -> SessionStatus:
    settings = get_settings()
    return SessionStatus(
        authenticated=(
            not settings.access_enabled
            or is_valid_session(request.cookies.get(SESSION_COOKIE), settings)
        )
    )


@router.post("/login", response_model=SessionStatus)
def login(
    response: Response,
    credentials: LoginRequest,
) -> SessionStatus:
    settings = get_settings()
    if not settings.access_enabled:
        return SessionStatus(authenticated=True)

    assert settings.app_access_password is not None
    expected = settings.app_access_password.get_secret_value()
    if not hmac.compare_digest(credentials.password, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The shared password is incorrect.",
        )

    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session(settings),
        max_age=SESSION_LIFETIME_SECONDS,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return SessionStatus(authenticated=True)


@router.post("/logout", response_model=SessionStatus)
def logout(response: Response) -> SessionStatus:
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    return SessionStatus(authenticated=False)


def is_valid_session(token: str | None, settings: Settings) -> bool:
    if not token or settings.app_session_secret is None:
        return False

    try:
        expires_text, supplied_signature = token.split(".", maxsplit=1)
        expires = int(expires_text)
        padded_signature = supplied_signature + "=" * (-len(supplied_signature) % 4)
        supplied = base64.urlsafe_b64decode(padded_signature)
    except (ValueError, TypeError):
        return False

    if expires <= int(time.time()):
        return False

    expected = _signature(expires_text, settings)
    return hmac.compare_digest(supplied, expected)


def create_session(settings: Settings) -> str:
    expires = str(int(time.time()) + SESSION_LIFETIME_SECONDS)
    signature = base64.urlsafe_b64encode(_signature(expires, settings)).decode("ascii").rstrip("=")
    return f"{expires}.{signature}"


def _signature(expires: str, settings: Settings) -> bytes:
    if settings.app_session_secret is None:
        raise RuntimeError(
            "APP_SESSION_SECRET must be configured when access protection is enabled."
        )
    return hmac.new(
        settings.app_session_secret.get_secret_value().encode("utf-8"),
        f"invoice-review:{expires}".encode("ascii"),
        hashlib.sha256,
    ).digest()
