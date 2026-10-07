from backend.app.schemas.general_ledger import (
    GeneralLedgerAccount,
    GLAccountCode,
)

GL_ACCOUNTS: tuple[GeneralLedgerAccount, ...] = (
    GeneralLedgerAccount(
        code="6000",
        name="Cleaning and Janitorial",
        description="Cleaning services and supplies.",
    ),
    GeneralLedgerAccount(
        code="6010",
        name="Building Maintenance and Repairs",
        description="Routine building repair and upkeep.",
    ),
    GeneralLedgerAccount(
        code="6020",
        name="Electrical Services",
        description="Electrical inspection, repair, and installation.",
    ),
    GeneralLedgerAccount(
        code="6030",
        name="Plumbing Services",
        description="Plumbing inspection, repair, and installation.",
    ),
    GeneralLedgerAccount(
        code="6040",
        name="HVAC and Climate Control",
        description="Heating, ventilation, and air-conditioning.",
    ),
    GeneralLedgerAccount(
        code="6050",
        name="Facilities Equipment and Tools",
        description="Equipment, tools, and related parts.",
    ),
    GeneralLedgerAccount(
        code="6060",
        name="Security Services",
        description="Facility security and access-control services.",
    ),
    GeneralLedgerAccount(
        code="6070",
        name="Waste Management and Recycling",
        description="Waste collection and recycling services.",
    ),
    GeneralLedgerAccount(
        code="6080",
        name="Utilities",
        description="Electricity, gas, water, and other utilities.",
    ),
    GeneralLedgerAccount(
        code="6090",
        name="Other Facilities Services",
        description="Facilities expenses not covered above.",
    ),
)


def get_gl_account(account_code: GLAccountCode) -> GeneralLedgerAccount:
    for account in GL_ACCOUNTS:
        if account.code == account_code:
            return account
    raise ValueError(f"Unknown general ledger account code: {account_code}")
