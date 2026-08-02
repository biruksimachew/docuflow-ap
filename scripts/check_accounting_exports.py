from __future__ import annotations

import csv
import io
import json
import time
from uuid import uuid4

import httpx

from scripts.auth_test_tokens import (
    authenticated_get,
    authorization_headers,
)
from tests.line_item_test_image import (
    create_line_item_invoice_image,
)


BASE_URL = "http://127.0.0.1:8000"


def invoice_png(
    *,
    invoice_number: str,
    purchase_order_number: str | None,
) -> bytes:
    image = create_line_item_invoice_image(
        invoice_number=invoice_number,
        purchase_order_number=(
            purchase_order_number
        ),
        marker="Accounting export fixture",
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def upload_and_wait(
    *,
    invoice_number: str,
    purchase_order_number: str | None,
) -> tuple[str, str]:
    upload = httpx.post(
        (
            f"{BASE_URL}"
            "/api/v1/documents/upload"
        ),
        files={
            "file": (
                f"{invoice_number}.png",
                invoice_png(
                    invoice_number=(
                        invoice_number
                    ),
                    purchase_order_number=(
                        purchase_order_number
                    ),
                ),
                "image/png",
            )
        },
        data={
            "source_channel": "WEB_UPLOAD",
        },
        timeout=30,
    )

    upload.raise_for_status()

    document_id = upload.json()[
        "document_id"
    ]

    terminal_status = None

    for _ in range(60):
        response = authenticated_get(
            (
                f"{BASE_URL}/api/v1/documents/"
                f"{document_id}/processing"
            ),
            role="AP_CLERK",
            timeout=20,
        )

        response.raise_for_status()

        terminal_status = response.json()[
            "document"
        ]["status"]

        if terminal_status in {
            "AUTO_APPROVED",
            "REVIEW_REQUIRED",
            "REJECTED",
            "FAILED",
        }:
            break

        time.sleep(2)

    if terminal_status is None:
        raise RuntimeError(
            "The document never reached a terminal state."
        )

    return (
        document_id,
        terminal_status,
    )


def generate_export(
    *,
    document_id: str,
    export_format: str,
) -> httpx.Response:
    return httpx.post(
        (
            f"{BASE_URL}/api/v1/documents/"
            f"{document_id}/exports"
        ),
        headers=authorization_headers(
            "AP_CLERK"
        ),
        json={
            "export_format": export_format,
        },
        timeout=30,
    )


def main() -> None:
    started_at = time.monotonic()

    approved_document_id, approved_status = (
        upload_and_wait(
            invoice_number=(
                f"EXP-{uuid4().hex[:8].upper()}"
            ),
            purchase_order_number="PO-7001",
        )
    )

    assert approved_status == "AUTO_APPROVED"

    first_json = generate_export(
        document_id=approved_document_id,
        export_format="JSON",
    )

    first_json.raise_for_status()

    first_payload = first_json.json()

    assert first_payload["status"] == "generated"

    json_export = first_payload["export"]

    assert json_export["status"] == "READY"

    assert (
        json_export["source_kind"]
        == "CANONICAL"
    )

    second_json = generate_export(
        document_id=approved_document_id,
        export_format="JSON",
    )

    second_json.raise_for_status()

    second_payload = second_json.json()

    assert second_payload["status"] == "reused"

    assert (
        second_payload["export"]["id"]
        == json_export["id"]
    )

    json_download = authenticated_get(
        (
            f"{BASE_URL}/api/v1/exports/"
            f"{json_export['id']}/download"
        ),
        role="AP_CLERK",
        timeout=20,
    )

    json_download.raise_for_status()

    parsed_json = json.loads(
        json_download.text
    )

    assert (
        parsed_json["document"]["id"]
        == approved_document_id
    )

    assert (
        parsed_json["invoice"]["header"][
            "purchase_order_number"
        ]
        == "PO-7001"
    )

    assert len(
        parsed_json["invoice"]["lines"]
    ) == 2

    csv_response = generate_export(
        document_id=approved_document_id,
        export_format="CSV",
    )

    csv_response.raise_for_status()

    csv_export = csv_response.json()[
        "export"
    ]

    csv_download = authenticated_get(
        (
            f"{BASE_URL}/api/v1/exports/"
            f"{csv_export['id']}/download"
        ),
        role="AP_CLERK",
        timeout=20,
    )

    csv_download.raise_for_status()

    csv_rows = list(
        csv.DictReader(
            io.StringIO(
                csv_download.text
            )
        )
    )

    assert len(csv_rows) == 2

    assert (
        csv_rows[0]["document_id"]
        == approved_document_id
    )

    export_list = authenticated_get(
        (
            f"{BASE_URL}/api/v1/documents/"
            f"{approved_document_id}/exports"
        ),
        role="ADMIN",
        timeout=20,
    )

    export_list.raise_for_status()

    assert export_list.json()["count"] == 2

    export_snapshot = authenticated_get(
        (
            f"{BASE_URL}/api/v1/exports/"
            f"{json_export['id']}"
        ),
        role="ADMIN",
        timeout=20,
    )

    export_snapshot.raise_for_status()

    event_types = [
        event["event_type"]
        for event in (
            export_snapshot.json()[
                "events"
            ]
        )
    ]

    assert "REQUESTED" in event_types
    assert "GENERATED" in event_types
    assert "DOWNLOADED" in event_types

    review_document_id, review_status = (
        upload_and_wait(
            invoice_number=(
                f"NOEXP-{uuid4().hex[:8].upper()}"
            ),
            purchase_order_number=None,
        )
    )

    assert review_status == "REVIEW_REQUIRED"

    blocked_export = generate_export(
        document_id=review_document_id,
        export_format="JSON",
    )

    assert blocked_export.status_code == 409

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "approved_document_id": (
                approved_document_id
            ),
            "approved_document_status": (
                approved_status
            ),
            "json_export_id": (
                json_export["id"]
            ),
            "json_export_ready": True,
            "json_idempotent_reuse": True,
            "json_sha256_preserved": bool(
                json_export[
                    "payload_sha256"
                ]
            ),
            "csv_export_id": (
                csv_export["id"]
            ),
            "csv_row_count": len(
                csv_rows
            ),
            "approved_only_guard": True,
            "audit_event_types": (
                event_types
            ),
            "elapsed_seconds": (
                elapsed_seconds
            ),
        }
    )


if __name__ == "__main__":
    main()
