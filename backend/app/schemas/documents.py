from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    """Response returned after document intake."""

    document_id: UUID
    status: str
    is_duplicate: bool

    original_filename: str
    sanitized_filename: str

    detected_media_type: str
    file_size_bytes: int
    page_count: int | None

    sha256: str
    quarantine_reason: str | None

    created_at: datetime