from typing import Literal

from pydantic import Field

from backend.app.schemas.shared import StrictSchema

GLAccountCode = Literal[
    "6000",
    "6010",
    "6020",
    "6030",
    "6040",
    "6050",
    "6060",
    "6070",
    "6080",
    "6090",
]


class GeneralLedgerAccount(StrictSchema):
    code: GLAccountCode
    name: str
    description: str


class GeneralLedgerSuggestion(StrictSchema):
    account_code: GLAccountCode = Field(
        description="One account code from Apex Facilities' fixed general ledger catalog."
    )
    reason: str = Field(
        min_length=1,
        max_length=240,
        description="A concise explanation based on the invoice's normalized fields.",
    )
