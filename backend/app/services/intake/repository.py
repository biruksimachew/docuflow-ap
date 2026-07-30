from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.db.database import engine


DOCUMENT_COLUMNS = """
    id,
    status,
    original_filename,
    sanitized_filename,
    detected_media_type,
    file_size_bytes,
    page_count,
    sha256,
    quarantine_reason,
    created_at
"""


async def find_document_by_sha256(
    sha256: str,
) -> dict[str, Any] | None:
    query = text(
        f"""
        select {DOCUMENT_COLUMNS}
        from public.documents
        where sha256 = :sha256
        limit 1
        """
    )

    async with engine.connect() as connection:
        result = await connection.execute(
            query,
            {
                "sha256": sha256,
            },
        )

        row = result.mappings().first()

    return dict(row) if row else None


async def create_document(
    *,
    document_id: str,
    status: str,
    source_channel: str,
    original_filename: str,
    sanitized_filename: str,
    declared_media_type: str | None,
    detected_media_type: str,
    file_size_bytes: int,
    page_count: int | None,
    sha256: str,
    storage_bucket: str,
    storage_object_key: str,
    quarantine_reason: str | None,
    source_message_id: str | None,
    source_attachment_id: str | None,
    source_metadata: dict[str, Any],
) -> dict[str, Any]:
    insert_document = text(
        f"""
        insert into public.documents (
            id,
            status,
            source_channel,
            original_filename,
            sanitized_filename,
            declared_media_type,
            detected_media_type,
            file_size_bytes,
            page_count,
            sha256,
            storage_provider,
            storage_bucket,
            storage_object_key,
            quarantine_reason
        )
        values (
            cast(:document_id as uuid),
            :status,
            :source_channel,
            :original_filename,
            :sanitized_filename,
            :declared_media_type,
            :detected_media_type,
            :file_size_bytes,
            :page_count,
            :sha256,
            's3',
            :storage_bucket,
            :storage_object_key,
            :quarantine_reason
        )
        returning {DOCUMENT_COLUMNS}
        """
    )

    insert_source = text(
        """
        insert into public.document_sources (
            document_id,
            source_channel,
            source_message_id,
            source_attachment_id,
            source_metadata
        )
        values (
            cast(:document_id as uuid),
            :source_channel,
            :source_message_id,
            :source_attachment_id,
            cast(:source_metadata as jsonb)
        )
        """
    )

    insert_audit = text(
        """
        insert into public.audit_events (
            document_id,
            event_type,
            actor_type,
            reason,
            payload
        )
        values (
            cast(:document_id as uuid),
            :event_type,
            'SYSTEM',
            :reason,
            cast(:payload as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        result = await connection.execute(
            insert_document,
            {
                "document_id": document_id,
                "status": status,
                "source_channel": source_channel,
                "original_filename": original_filename,
                "sanitized_filename": sanitized_filename,
                "declared_media_type": declared_media_type,
                "detected_media_type": detected_media_type,
                "file_size_bytes": file_size_bytes,
                "page_count": page_count,
                "sha256": sha256,
                "storage_bucket": storage_bucket,
                "storage_object_key": storage_object_key,
                "quarantine_reason": quarantine_reason,
            },
        )

        row = result.mappings().one()

        await connection.execute(
            insert_source,
            {
                "document_id": document_id,
                "source_channel": source_channel,
                "source_message_id": source_message_id,
                "source_attachment_id": source_attachment_id,
                "source_metadata": json.dumps(source_metadata),
            },
        )

        event_type = (
            "DOCUMENT_QUARANTINED"
            if status == "QUARANTINED"
            else "DOCUMENT_RECEIVED"
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "event_type": event_type,
                "reason": quarantine_reason,
                "payload": json.dumps(
                    {
                        "source_channel": source_channel,
                        "sha256": sha256,
                        "detected_media_type": detected_media_type,
                        "file_size_bytes": file_size_bytes,
                        "page_count": page_count,
                        "storage_bucket": storage_bucket,
                        "storage_object_key": storage_object_key,
                    }
                ),
            },
        )

    return dict(row)


async def record_duplicate_intake(
    *,
    document_id: str,
    source_channel: str,
    source_message_id: str | None,
    source_attachment_id: str | None,
    source_metadata: dict[str, Any],
    sha256: str,
) -> None:
    insert_source = text(
        """
        insert into public.document_sources (
            document_id,
            source_channel,
            source_message_id,
            source_attachment_id,
            source_metadata
        )
        values (
            cast(:document_id as uuid),
            :source_channel,
            :source_message_id,
            :source_attachment_id,
            cast(:source_metadata as jsonb)
        )
        on conflict do nothing
        """
    )

    insert_audit = text(
        """
        insert into public.audit_events (
            document_id,
            event_type,
            actor_type,
            reason,
            payload
        )
        values (
            cast(:document_id as uuid),
            'SOURCE_DUPLICATE_DETECTED',
            'SYSTEM',
            'An existing document matched the uploaded SHA-256 checksum.',
            cast(:payload as jsonb)
        )
        """
    )

    async with engine.begin() as connection:
        await connection.execute(
            insert_source,
            {
                "document_id": document_id,
                "source_channel": source_channel,
                "source_message_id": source_message_id,
                "source_attachment_id": source_attachment_id,
                "source_metadata": json.dumps(source_metadata),
            },
        )

        await connection.execute(
            insert_audit,
            {
                "document_id": document_id,
                "payload": json.dumps(
                    {
                        "source_channel": source_channel,
                        "source_message_id": source_message_id,
                        "source_attachment_id": source_attachment_id,
                        "sha256": sha256,
                    }
                ),
            },
        )