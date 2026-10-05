from pathlib import Path
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from pydantic import PrivateAttr, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.app.providers.azure_document_intelligence import (
    map_invoice_result,
    map_receipt_result,
)
from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.receipt.model import Receipt

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class DocumentIntelligenceService(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_document_intelligence_endpoint: str
    azure_document_intelligence_key: SecretStr

    _client: DocumentIntelligenceClient = PrivateAttr()

    def __init__(self, **values: Any) -> None:
        super().__init__(**values)
        self._client = DocumentIntelligenceClient(
            endpoint=self.azure_document_intelligence_endpoint,
            credential=AzureKeyCredential(
                self.azure_document_intelligence_key.get_secret_value()
            ),
        )

    def analyze_invoice(self, document_path: Path) -> AnalyzeResult:
        if not document_path.is_file():
            raise FileNotFoundError(f"Invoice document not found: {document_path}")

        poller = self._client.begin_analyze_document(
            model_id="prebuilt-invoice",
            body=AnalyzeDocumentRequest(bytes_source=document_path.read_bytes()),
        )
        return poller.result()

    def analyze_receipt(self, document_path: Path) -> AnalyzeResult:
        if not document_path.is_file():
            raise FileNotFoundError(f"Receipt document not found: {document_path}")

        poller = self._client.begin_analyze_document(
            model_id="prebuilt-receipt",
            body=AnalyzeDocumentRequest(bytes_source=document_path.read_bytes()),
        )
        return poller.result()

    def extract_invoice(self, document_path: Path) -> Invoice:
        return map_invoice_result(self.analyze_invoice(document_path))

    def extract_receipt(self, document_path: Path) -> Receipt:
        return map_receipt_result(self.analyze_receipt(document_path))

    def close(self) -> None:
        self._client.close()
