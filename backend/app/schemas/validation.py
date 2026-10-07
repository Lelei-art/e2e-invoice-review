from typing import Literal

from backend.app.schemas.shared import StrictSchema


class ValidationFinding(StrictSchema):
    code: str
    field: str
    severity: Literal["error", "warning"]
    message: str
