from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "accounting-export-v1"


def build_idempotency_key(
    *,
    document_id: str,
    export_format: str,
    source_kind: str,
    source_version: str,
) -> str:
    material = "|".join(
        (
            SCHEMA_VERSION,
            document_id,
            export_format,
            source_kind,
            source_version,
        )
    )

    return hashlib.sha256(
        material.encode("utf-8")
    ).hexdigest()


def render_export(
    *,
    export_id: str,
    export_format: str,
    source: dict[str, Any],
) -> dict[str, Any]:
    normalized_format = export_format.strip().upper()

    if normalized_format == "JSON":
        payload = _render_json(
            export_id=export_id,
            source=source,
        )
        content_type = "application/json"
        extension = "json"
        row_count = len(
            source["invoice"]["lines"]
        )
    elif normalized_format == "CSV":
        payload = _render_csv(
            export_id=export_id,
            source=source,
        )
        content_type = "text/csv"
        extension = "csv"
        row_count = max(
            1,
            len(source["invoice"]["lines"]),
        )
    else:
        raise ValueError(
            "Accounting export format must be JSON or CSV."
        )

    invoice_number = (
        source["invoice"]["header"].get(
            "invoice_number"
        )
        or source["document_id"]
    )

    safe_invoice_number = re.sub(
        r"[^A-Za-z0-9._-]+",
        "-",
        str(invoice_number),
    ).strip("-")

    if not safe_invoice_number:
        safe_invoice_number = source[
            "document_id"
        ]

    return {
        "schema_version": SCHEMA_VERSION,
        "payload_text": payload,
        "payload_sha256": hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest(),
        "content_type": content_type,
        "file_name": (
            f"docuflow-{safe_invoice_number}."
            f"{extension}"
        ),
        "row_count": row_count,
    }


def _render_json(
    *,
    export_id: str,
    source: dict[str, Any],
) -> str:
    document = {
        "schema_version": SCHEMA_VERSION,
        "export_id": export_id,
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "document": {
            "id": source["document_id"],
            "original_filename": source.get(
                "original_filename"
            ),
            "sha256": source.get(
                "document_sha256"
            ),
        },
        "source": {
            "kind": source["source_kind"],
            "version": source["source_version"],
            "decision_run_id": source.get(
                "decision_run_id"
            ),
            "review_case_id": source.get(
                "review_case_id"
            ),
        },
        "invoice": source["invoice"],
    }

    return json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _render_csv(
    *,
    export_id: str,
    source: dict[str, Any],
) -> str:
    header = source["invoice"]["header"]
    lines = source["invoice"]["lines"]

    field_names = [
        "schema_version",
        "export_id",
        "document_id",
        "original_filename",
        "document_sha256",
        "source_kind",
        "source_version",
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "due_date",
        "purchase_order_number",
        "currency",
        "subtotal",
        "discount_amount",
        "shipping_amount",
        "tax_amount",
        "total_amount",
        "line_number",
        "description",
        "supplier_sku",
        "quantity",
        "unit_of_measure",
        "unit_price",
        "tax_rate",
        "line_total",
        "line_currency",
    ]

    buffer = io.StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        buffer,
        fieldnames=field_names,
        extrasaction="ignore",
    )

    writer.writeheader()

    export_lines = lines or [
        {}
    ]

    for line in export_lines:
        row = {
            "schema_version": SCHEMA_VERSION,
            "export_id": export_id,
            "document_id": source[
                "document_id"
            ],
            "original_filename": source.get(
                "original_filename"
            ),
            "document_sha256": source.get(
                "document_sha256"
            ),
            "source_kind": source[
                "source_kind"
            ],
            "source_version": source[
                "source_version"
            ],
            "vendor_name": header.get(
                "vendor_name"
            ),
            "invoice_number": header.get(
                "invoice_number"
            ),
            "invoice_date": header.get(
                "invoice_date"
            ),
            "due_date": header.get(
                "due_date"
            ),
            "purchase_order_number": header.get(
                "purchase_order_number"
            ),
            "currency": header.get(
                "currency"
            ),
            "subtotal": header.get(
                "subtotal"
            ),
            "discount_amount": header.get(
                "discount_amount"
            ),
            "shipping_amount": header.get(
                "shipping_amount"
            ),
            "tax_amount": header.get(
                "tax_amount"
            ),
            "total_amount": header.get(
                "total_amount"
            ),
            "line_number": line.get(
                "line_number"
            ),
            "description": line.get(
                "description"
            ),
            "supplier_sku": line.get(
                "supplier_sku"
            ),
            "quantity": line.get(
                "quantity"
            ),
            "unit_of_measure": line.get(
                "unit_of_measure"
            ),
            "unit_price": line.get(
                "unit_price"
            ),
            "tax_rate": line.get(
                "tax_rate"
            ),
            "line_total": line.get(
                "line_total"
            ),
            "line_currency": line.get(
                "currency"
            ),
        }

        writer.writerow(
            {
                key: _safe_csv_cell(value)
                for key, value in row.items()
            }
        )

    return buffer.getvalue()


def _safe_csv_cell(
    value: Any,
) -> Any:
    if not isinstance(value, str):
        return value

    if value.startswith(
        (
            "=",
            "+",
            "-",
            "@",
            "\t",
            "\r",
        )
    ):
        return "'" + value

    return value
