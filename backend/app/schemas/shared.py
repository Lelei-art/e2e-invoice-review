from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaxDetail(StrictSchema):
    description: str | None = None
    rate: Decimal | None = None
    amount: Decimal | None = None
    net_amount: Decimal | None = None
    field_confidence: dict[str, float] = Field(default_factory=dict)


class ExtractionConflict(StrictSchema):
    field: str
    document_intelligence_value: str
    azure_openai_value: str


class FieldProvenance(StrictSchema):
    source: Literal["document_intelligence", "azure_openai", "missing"]
