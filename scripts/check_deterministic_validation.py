import io
import time
from uuid import uuid4

import httpx
from PIL import ImageDraw

from tests.ocr_test_image import (
    create_test_invoice_image,
)


def create_unique_invoice_png() -> bytes:
    image = create_test_invoice_image()

    draw = ImageDraw.Draw(
        image
    )

    draw.text(
        (1020, 950),
        f"Validation run {uuid4()}",
        fill="black",
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def main() -> None:
    started_at = time.monotonic()

    upload_response = httpx.post(
        (
            "http://127.0.0.1:8000"
            "/api/v1/documents/upload"
        ),
        files={
            "file": (
                "Meridian Validation Invoice.png",
                create_unique_invoice_png(),
                "image/png",
            )
        },
        data={
            "source_channel": "WEB_UPLOAD",
        },
        timeout=30,
    )

    upload_response.raise_for_status()

    upload_payload = (
        upload_response.json()
    )

    assert upload_response.status_code == 201
    assert upload_payload["status"] == "RECEIVED"
    assert (
        upload_payload["processing_enqueued"]
        is True
    )

    document_id = upload_payload[
        "document_id"
    ]

    processing_snapshot = None

    for _ in range(60):
        response = httpx.get(
            (
                "http://127.0.0.1:8000"
                f"/api/v1/documents/{document_id}"
                "/processing"
            ),
            timeout=20,
        )

        response.raise_for_status()

        processing_snapshot = response.json()

        document_status = (
            processing_snapshot[
                "document"
            ]["status"]
        )

        if document_status in {
            "REVIEW_REQUIRED",
            "FAILED",
        }:
            break

        time.sleep(2)

    if processing_snapshot is None:
        raise RuntimeError(
            "No processing snapshot was returned."
        )

    document = processing_snapshot[
        "document"
    ]

    if document["status"] == "FAILED":
        raise RuntimeError(
            {
                "error_code": document[
                    "last_error_code"
                ],
                "error_message": document[
                    "last_error_message"
                ],
            }
        )

    assert (
        document["status"]
        == "REVIEW_REQUIRED"
    )

    validation_response = httpx.get(
        (
            "http://127.0.0.1:8000"
            f"/api/v1/documents/{document_id}"
            "/validation"
        ),
        timeout=20,
    )

    validation_response.raise_for_status()

    snapshot = validation_response.json()

    validation_run = snapshot[
        "validation_run"
    ]

    assert validation_run is not None
    assert validation_run["status"] == "SUCCEEDED"

    assert (
        validation_run["ruleset_version"]
        == "header-rules-v1"
    )

    assert (
        validation_run["overall_outcome"]
        == "PASSED_CONTROLS"
    )

    assert validation_run["passed_count"] == 6
    assert validation_run["warning_count"] == 0
    assert validation_run["failed_count"] == 0
    assert validation_run["blocking_count"] == 0

    results = {
        result["rule_id"]: result
        for result in snapshot[
            "validation_results"
        ]
    }

    expected_rule_ids = {
        "VAL-01",
        "VAL-02",
        "VAL-05",
        "VAL-06",
        "VAL-07",
        "VAL-08",
    }

    assert set(results) == expected_rule_ids

    for rule_id in expected_rule_ids:
        rule = results[rule_id]

        assert rule["result"] == "PASS"
        assert rule["blocking"] is False
        assert rule["message"]

    arithmetic = results["VAL-02"]

    assert (
        arithmetic["expected_value"][
            "calculated_total"
        ]
        == "138.00"
    )

    assert (
        arithmetic["actual_value"][
            "stated_total"
        ]
        == "138.00"
    )

    assert (
        arithmetic["actual_value"][
            "difference"
        ]
        == "0.00"
    )

    normalization = results["VAL-08"]

    assert (
        normalization["actual_value"][
            "canonical_invoice_number"
        ]
        == "INV-1001"
    )

    elapsed_seconds = round(
        time.monotonic() - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "document_id": document_id,
            "document_status": document["status"],
            "validation_status": (
                validation_run["status"]
            ),
            "ruleset_version": (
                validation_run[
                    "ruleset_version"
                ]
            ),
            "overall_outcome": (
                validation_run[
                    "overall_outcome"
                ]
            ),
            "rules_executed": len(
                results
            ),
            "blocking_count": (
                validation_run[
                    "blocking_count"
                ]
            ),
            "header_arithmetic_difference": (
                arithmetic["actual_value"][
                    "difference"
                ]
            ),
            "expected_actual_evidence_preserved": True,
            "elapsed_seconds": elapsed_seconds,
        }
    )


if __name__ == "__main__":
    main()