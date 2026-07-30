from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import filetype
from pypdf import PdfReader
from pypdf.errors import PdfReadError


MIME_EXTENSION_MAP = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


class FileValidationError(Exception):
    """A safe validation error suitable for an API response."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
    ) -> None:
        super().__init__(message)

        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ValidatedUpload:
    content: bytes

    original_filename: str
    sanitized_filename: str

    declared_media_type: str | None
    detected_media_type: str

    file_size_bytes: int
    page_count: int | None

    sha256: str
    quarantine_reason: str | None


def sanitize_filename(
    original_filename: str,
    detected_media_type: str,
) -> str:
    """Create a safe storage filename while preserving metadata separately."""

    basename = Path(original_filename).name

    normalized = unicodedata.normalize("NFKD", basename)
    ascii_name = normalized.encode(
        "ascii",
        "ignore",
    ).decode("ascii")

    stem = Path(ascii_name).stem

    stem = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        stem,
    )

    stem = re.sub(r"-+", "-", stem)
    stem = stem.strip("._-")

    if not stem:
        stem = "invoice"

    stem = stem[:120]

    extension = MIME_EXTENSION_MAP[detected_media_type]

    return f"{stem}{extension}"


def normalize_declared_media_type(
    declared_media_type: str | None,
) -> str | None:
    if not declared_media_type:
        return None

    normalized = declared_media_type.split(";")[0].strip().lower()

    aliases = {
        "image/jpg": "image/jpeg",
        "application/x-pdf": "application/pdf",
    }

    return aliases.get(normalized, normalized)


def detect_media_type(content: bytes) -> str | None:
    kind = filetype.guess(content)

    if kind is None:
        if content.startswith(b"%PDF-"):
            return "application/pdf"

        return None

    return kind.mime.lower()


def inspect_pdf(
    content: bytes,
    maximum_pages: int,
) -> tuple[int | None, str | None]:
    try:
        reader = PdfReader(
            io.BytesIO(content),
            strict=False,
        )
    except (PdfReadError, ValueError, OSError):
        return None, "CORRUPTED_PDF"

    if reader.is_encrypted:
        return None, "PASSWORD_PROTECTED_PDF"

    try:
        page_count = len(reader.pages)
    except (PdfReadError, ValueError, OSError):
        return None, "CORRUPTED_PDF"

    if page_count < 1:
        return None, "PDF_HAS_NO_PAGES"

    if page_count > maximum_pages:
        raise FileValidationError(
            status_code=413,
            code="PAGE_LIMIT_EXCEEDED",
            message=(
                f"The document contains {page_count} pages. "
                f"The configured maximum is {maximum_pages}."
            ),
        )

    return page_count, None


def validate_upload(
    *,
    content: bytes,
    original_filename: str,
    declared_media_type: str | None,
    maximum_size_bytes: int,
    maximum_pages: int,
    allowed_media_types: set[str],
) -> ValidatedUpload:
    if not content:
        raise FileValidationError(
            status_code=422,
            code="EMPTY_FILE",
            message="The uploaded file is empty.",
        )

    file_size_bytes = len(content)

    if file_size_bytes > maximum_size_bytes:
        raise FileValidationError(
            status_code=413,
            code="FILE_SIZE_LIMIT_EXCEEDED",
            message=(
                f"The file exceeds the configured "
                f"{maximum_size_bytes} byte limit."
            ),
        )

    detected_media_type = detect_media_type(content)

    if (
        detected_media_type is None
        or detected_media_type not in allowed_media_types
    ):
        raise FileValidationError(
            status_code=415,
            code="UNSUPPORTED_FILE_SIGNATURE",
            message=(
                "The file signature is not a supported "
                "PDF, JPEG, or PNG document."
            ),
        )

    normalized_declared_type = normalize_declared_media_type(
        declared_media_type
    )

    generic_declared_types = {
        None,
        "",
        "application/octet-stream",
        "binary/octet-stream",
    }

    if (
        normalized_declared_type not in generic_declared_types
        and normalized_declared_type != detected_media_type
    ):
        raise FileValidationError(
            status_code=415,
            code="FILE_TYPE_MISMATCH",
            message=(
                "The declared content type does not match "
                "the actual file signature."
            ),
        )

    page_count: int | None
    quarantine_reason: str | None = None

    if detected_media_type == "application/pdf":
        page_count, quarantine_reason = inspect_pdf(
            content,
            maximum_pages,
        )
    else:
        page_count = 1

    digest = hashlib.sha256(content).hexdigest()

    safe_filename = sanitize_filename(
        original_filename,
        detected_media_type,
    )

    return ValidatedUpload(
        content=content,
        original_filename=original_filename,
        sanitized_filename=safe_filename,
        declared_media_type=normalized_declared_type,
        detected_media_type=detected_media_type,
        file_size_bytes=file_size_bytes,
        page_count=page_count,
        sha256=digest,
        quarantine_reason=quarantine_reason,
    )