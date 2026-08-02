import csv
import io
import json

from app.services.accounting_exports.renderer import (
    SCHEMA_VERSION,
    build_idempotency_key,
    render_export,
)


def source() -> dict:
    return {
        "document_id": (
            "00000000-0000-0000-0000-000000000001"
        ),
        "original_filename": "invoice.png",
        "document_sha256": "a" * 64,
        "source_kind": "CANONICAL",
        "source_version": (
            "decision-run:test"
        ),
        "decision_run_id": (
            "00000000-0000-0000-0000-000000000002"
        ),
        "review_case_id": None,
        "invoice": {
            "header": {
                "vendor_name": (
                    "Meridian Office Supplies"
                ),
                "invoice_number": "INV-1001",
                "invoice_date": "2026-07-30",
                "due_date": None,
                "purchase_order_number": (
                    "PO-7001"
                ),
                "currency": "USD",
                "subtotal": "120.00",
                "discount_amount": "0.00",
                "shipping_amount": "0.00",
                "tax_amount": "18.00",
                "total_amount": "138.00",
            },
            "lines": [
                {
                    "id": "line-1",
                    "line_number": 1,
                    "description": (
                        "Printer Paper"
                    ),
                    "supplier_sku": None,
                    "quantity": "2",
                    "unit_of_measure": None,
                    "unit_price": "50.00",
                    "tax_rate": None,
                    "line_total": "100.00",
                    "currency": "USD",
                },
                {
                    "id": "line-2",
                    "line_number": 2,
                    "description": "Blue Pens",
                    "supplier_sku": None,
                    "quantity": "1",
                    "unit_of_measure": None,
                    "unit_price": "20.00",
                    "tax_rate": None,
                    "line_total": "20.00",
                    "currency": "USD",
                },
            ],
        },
    }


def test_idempotency_key_is_stable() -> None:
    first = build_idempotency_key(
        document_id=source()[
            "document_id"
        ],
        export_format="JSON",
        source_kind="CANONICAL",
        source_version="decision-run:test",
    )

    second = build_idempotency_key(
        document_id=source()[
            "document_id"
        ],
        export_format="JSON",
        source_kind="CANONICAL",
        source_version="decision-run:test",
    )

    assert first == second


def test_export_format_changes_key() -> None:
    json_key = build_idempotency_key(
        document_id=source()[
            "document_id"
        ],
        export_format="JSON",
        source_kind="CANONICAL",
        source_version="decision-run:test",
    )

    csv_key = build_idempotency_key(
        document_id=source()[
            "document_id"
        ],
        export_format="CSV",
        source_kind="CANONICAL",
        source_version="decision-run:test",
    )

    assert json_key != csv_key


def test_json_export_is_structured() -> None:
    rendered = render_export(
        export_id="export-1",
        export_format="JSON",
        source=source(),
    )

    payload = json.loads(
        rendered["payload_text"]
    )

    assert (
        payload["schema_version"]
        == SCHEMA_VERSION
    )

    assert (
        payload["invoice"]["header"][
            "invoice_number"
        ]
        == "INV-1001"
    )

    assert len(
        payload["invoice"]["lines"]
    ) == 2

    assert (
        rendered["content_type"]
        == "application/json"
    )


def test_csv_export_has_one_row_per_line() -> None:
    rendered = render_export(
        export_id="export-1",
        export_format="CSV",
        source=source(),
    )

    rows = list(
        csv.DictReader(
            io.StringIO(
                rendered["payload_text"]
            )
        )
    )

    assert len(rows) == 2

    assert (
        rows[0]["invoice_number"]
        == "INV-1001"
    )

    assert (
        rows[0]["description"]
        == "Printer Paper"
    )

    assert (
        rows[1]["description"]
        == "Blue Pens"
    )


def test_export_file_name_is_safe() -> None:
    data = source()

    data["invoice"]["header"][
        "invoice_number"
    ] = "INV/1001 #A"

    rendered = render_export(
        export_id="export-1",
        export_format="JSON",
        source=data,
    )

    assert (
        rendered["file_name"]
        == "docuflow-INV-1001-A.json"
    )


def test_csv_formula_injection_is_escaped() -> None:
    data = source()

    data["invoice"]["lines"][0][
        "description"
    ] = "=HYPERLINK(""bad"")"

    rendered = render_export(
        export_id="export-1",
        export_format="CSV",
        source=data,
    )

    rows = list(
        csv.DictReader(
            io.StringIO(
                rendered["payload_text"]
            )
        )
    )

    assert rows[0]["description"].startswith(
        "'="
    )
