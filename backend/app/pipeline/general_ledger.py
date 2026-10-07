from backend.app.providers.azure_gl_categorizer import suggest_general_ledger
from backend.app.schemas.general_ledger import GeneralLedgerSuggestion
from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.receipt.model import Receipt


class GeneralLedgerSuggestionStep:
    """Suggest a fixed-catalog ledger account from normalized document fields."""

    async def run(
        self, *, document: Invoice | Receipt
    ) -> GeneralLedgerSuggestion:
        return await suggest_general_ledger(document)
