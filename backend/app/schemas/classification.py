from typing import Literal

from pydantic import Field

from backend.app.schemas.shared import StrictSchema


class DocumentClassification(StrictSchema):
    document_type: Literal["invoice", "receipt", "other"] = Field(
        description="Use other for unsupported or uncertain documents."
    )
    reason: str = Field(
        min_length=1,
        max_length=200,
        description="A concise reason for the selected document type.",
    )
