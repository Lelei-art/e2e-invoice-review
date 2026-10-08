import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from backend.app.config import get_settings
from backend.app.invoices.validation import duplicate_fingerprint
from backend.app.schemas.invoice.model import Invoice
from backend.app.schemas.pipeline import DocumentProcessingResult
from backend.app.schemas.receipt.model import Receipt
from backend.app.schemas.review import DocumentReview

DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "invoice-review.sqlite3"
FinancialDocument = Invoice | Receipt


class DocumentRepository:
    """Persist review records and the fingerprints used for duplicate checks."""

    def __init__(self, database_path: Path = DATABASE_PATH) -> None:
        self._database_path = database_path

    def create_review(
        self,
        review: DocumentReview,
        document: FinancialDocument | None,
    ) -> bool:
        self._initialize()
        with closing(self._connect()) as connection:
            with connection:
                duplicate = self._has_duplicate(
                    connection,
                    document=document,
                    excluding_review_id=None,
                )
                if document is not None:
                    self._insert_fingerprint(
                        connection,
                        document=document,
                        review_id=review.id,
                    )
                connection.execute(
                    """
                    INSERT INTO document_reviews (
                        id, filename, status, result_json,
                        selected_gl_account_code, decision_reason,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._review_values(review),
                )
        return duplicate

    def get_review(self, review_id: str) -> DocumentReview | None:
        self._initialize()
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM document_reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
        return self._to_review(row) if row is not None else None

    def list_reviews(self) -> list[DocumentReview]:
        self._initialize()
        with closing(self._connect()) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM document_reviews ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._to_review(row) for row in rows]

    def has_duplicate(
        self,
        document: FinancialDocument,
        *,
        excluding_review_id: str,
    ) -> bool:
        self._initialize()
        with closing(self._connect()) as connection:
            return self._has_duplicate(
                connection,
                document=document,
                excluding_review_id=excluding_review_id,
            )

    def save_review(
        self,
        review: DocumentReview,
        document: FinancialDocument | None,
    ) -> None:
        self._initialize()
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE document_reviews
                    SET filename = ?, status = ?, result_json = ?,
                        selected_gl_account_code = ?, decision_reason = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        review.filename,
                        review.status,
                        review.result.model_dump_json(),
                        review.selected_gl_account_code,
                        review.decision_reason,
                        review.updated_at.isoformat(),
                        review.id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise LookupError(f"Review {review.id!r} was not found.")
                connection.execute(
                    "DELETE FROM processed_documents WHERE review_id = ?",
                    (review.id,),
                )
                if document is not None:
                    self._insert_fingerprint(
                        connection,
                        document=document,
                        review_id=review.id,
                    )

    def delete_review(self, review_id: str) -> bool:
        self._initialize()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "DELETE FROM processed_documents WHERE review_id = ?",
                    (review_id,),
                )
                cursor = connection.execute(
                    "DELETE FROM document_reviews WHERE id = ?",
                    (review_id,),
                )
        return cursor.rowcount > 0

    def record_processed_document(self, document: FinancialDocument) -> bool:
        """Keep the standalone processing example's duplicate-history behavior."""
        self._initialize()
        with closing(self._connect()) as connection:
            with connection:
                duplicate = self._has_duplicate(
                    connection,
                    document=document,
                    excluding_review_id=None,
                )
                self._insert_fingerprint(
                    connection,
                    document=document,
                    review_id=None,
                )
        return duplicate

    def _initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS processed_documents (
                        id INTEGER PRIMARY KEY,
                        document_type TEXT NOT NULL,
                        duplicate_fingerprint TEXT,
                        processed_at TEXT NOT NULL,
                        review_id TEXT
                    )
                    """
                )
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(processed_documents)"
                    ).fetchall()
                }
                if "review_id" not in columns:
                    connection.execute(
                        "ALTER TABLE processed_documents ADD COLUMN review_id TEXT"
                    )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS ix_processed_documents_duplicate
                    ON processed_documents (document_type, duplicate_fingerprint)
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_reviews (
                        id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        status TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        selected_gl_account_code TEXT,
                        decision_reason TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        vfs = get_settings().sqlite_vfs
        if vfs is None:
            return sqlite3.connect(self._database_path, timeout=30)
        database_uri = f"{self._database_path.resolve().as_uri()}?vfs={vfs}"
        return sqlite3.connect(database_uri, uri=True, timeout=30)

    def _has_duplicate(
        self,
        connection: sqlite3.Connection,
        *,
        document: FinancialDocument | None,
        excluding_review_id: str | None,
    ) -> bool:
        if document is None:
            return False
        fingerprint = duplicate_fingerprint(document)
        if fingerprint is None:
            return False
        query = """
            SELECT 1 FROM processed_documents
            WHERE document_type = ? AND duplicate_fingerprint = ?
        """
        values: tuple[str, ...] = (document.document_type, fingerprint)
        if excluding_review_id is not None:
            query += " AND (review_id IS NULL OR review_id != ?)"
            values += (excluding_review_id,)
        query += " LIMIT 1"
        return connection.execute(query, values).fetchone() is not None

    def _insert_fingerprint(
        self,
        connection: sqlite3.Connection,
        *,
        document: FinancialDocument,
        review_id: str | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO processed_documents
                (document_type, duplicate_fingerprint, processed_at, review_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                document.document_type,
                duplicate_fingerprint(document),
                datetime.now(UTC).isoformat(),
                review_id,
            ),
        )

    def _review_values(self, review: DocumentReview) -> tuple[str, ...]:
        return (
            review.id,
            review.filename,
            review.status,
            review.result.model_dump_json(),
            review.selected_gl_account_code or "",
            review.decision_reason or "",
            review.created_at.isoformat(),
            review.updated_at.isoformat(),
        )

    def _to_review(self, row: sqlite3.Row) -> DocumentReview:
        return DocumentReview(
            id=row["id"],
            filename=row["filename"],
            status=row["status"],
            result=DocumentProcessingResult.model_validate_json(row["result_json"]),
            selected_gl_account_code=row["selected_gl_account_code"] or None,
            decision_reason=row["decision_reason"] or None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
