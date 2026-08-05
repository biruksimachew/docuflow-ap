from __future__ import annotations

import asyncio
import os
import time
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
)

from scripts.check_review_corrections_and_resolution import (
    create_review_document,
)
from scripts.provision_local_auth_users import (
    provision_local_auth_users,
)


FRONTEND_URL = "http://frontend:3000"


def wait_for_frontend() -> None:
    last_error: Exception | None = None

    for _ in range(60):
        try:
            response = httpx.get(
                f"{FRONTEND_URL}/api/health",
                timeout=10,
            )

            if response.status_code == 200:
                return
        except Exception as exc:
            last_error = exc

        time.sleep(2)

    raise RuntimeError(
        "Frontend did not become ready."
    ) from last_error


def create_review_fixture(
    *,
    max_attempts: int = 3,
) -> tuple[str, str]:
    failures: list[str] = []

    for _ in range(max_attempts):
        invoice_number = (
            "UI-"
            f"{uuid4().hex[:8].upper()}"
        )

        try:
            return create_review_document(
                invoice_number
            )
        except Exception as exc:
            failures.append(
                f"{invoice_number}: {exc}"
            )

    raise RuntimeError(
        "Could not create an interactive review fixture. "
        f"Failures: {failures}"
    )


async def force_delivery_failed(
    delivery_id: str,
) -> None:
    database_url = os.environ[
        "DATABASE_URL"
    ]

    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
    )

    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    update public.notification_deliveries
                    set
                        status = 'FAILED',
                        delivered_at = null,
                        next_attempt_at = null,
                        last_error_code =
                            'INTERACTIVE_TEST_FAILURE',
                        last_error_message =
                            'Synthetic failed delivery for retry coverage.'
                    where id =
                        cast(:delivery_id as uuid)
                    """
                ),
                {
                    "delivery_id": (
                        delivery_id
                    ),
                },
            )
    finally:
        await engine.dispose()


def operation(
    client: httpx.Client,
    path: str,
    *,
    payload: dict | None = None,
) -> httpx.Response:
    request_kwargs: dict = {
        "timeout": 60,
    }

    if payload is not None:
        request_kwargs["json"] = payload

    return client.post(
        (
            "/api/operations/"
            f"{path.lstrip('/')}"
        ),
        **request_kwargs,
    )


def wait_for_delivery(
    client: httpx.Client,
    delivery_id: str,
    *,
    timeout_seconds: int = 60,
) -> dict:
    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    latest: dict | None = None

    while time.monotonic() < deadline:
        response = client.get(
            (
                "/api/operations/"
                f"notifications/{delivery_id}"
            ),
            timeout=30,
        )

        response.raise_for_status()
        latest = response.json()

        current_status = latest[
            "delivery"
        ]["status"]

        if current_status in {
            "SUCCEEDED",
            "FAILED",
        }:
            return latest

        time.sleep(1)

    raise RuntimeError(
        "Notification did not reach a terminal state. "
        f"Latest: {latest}"
    )


def main() -> None:
    started_at = time.monotonic()

    asyncio.run(
        provision_local_auth_users()
    )

    wait_for_frontend()

    (
        document_id,
        review_case_id,
    ) = create_review_fixture()

    password = os.getenv(
        "DOCUFLOW_LOCAL_AUTH_PASSWORD",
        "DocuFlowLocal!2026",
    )

    with httpx.Client(
        base_url=FRONTEND_URL,
        follow_redirects=True,
        timeout=60,
    ) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "email": (
                    "administrator@"
                    "docuflow.local"
                ),
                "password": password,
            },
        )

        login.raise_for_status()

        document_page = client.get(
            f"/documents/{document_id}"
        )

        document_page.raise_for_status()

        assert "Review controls" in (
            document_page.text
        )
        assert "Correction workspace" in (
            document_page.text
        )
        assert "Audit trail" in (
            document_page.text
        )
        assert "Generate export" in (
            document_page.text
        )

        invoices_page = client.get(
            (
                "/invoices"
                "?sort=vendor_name"
                "&direction=asc"
                "&page=1"
            )
        )

        invoices_page.raise_for_status()

        assert "Sort by" in invoices_page.text
        assert "Page" in invoices_page.text

        reviews_page = client.get(
            (
                "/reviews"
                "?owner=UNCLAIMED"
                "&sort=priority"
                "&direction=asc"
                "&page=1"
            )
        )

        reviews_page.raise_for_status()

        assert "Ownership" in (
            reviews_page.text
        )

        claim = operation(
            client,
            (
                f"reviews/{review_case_id}"
                "/claim"
            ),
        )

        claim.raise_for_status()

        note = operation(
            client,
            (
                f"reviews/{review_case_id}"
                "/notes"
            ),
            payload={
                "note": (
                    "Interactive workspace "
                    "smoke-test evidence."
                )
            },
        )

        note.raise_for_status()

        correction = operation(
            client,
            (
                f"reviews/{review_case_id}"
                "/corrections"
            ),
            payload={
                "target_type": "HEADER",
                "line_item_id": None,
                "field_name": (
                    "purchase_order_number"
                ),
                "corrected_value": (
                    "PO-7001"
                ),
                "reason": (
                    "Verified in the procurement "
                    "register through the operations "
                    "workspace."
                ),
                "apply_immediately": False,
            },
        )

        correction.raise_for_status()

        correction_id = correction.json()[
            "correction"
        ]["id"]

        apply_response = operation(
            client,
            (
                f"reviews/{review_case_id}"
                f"/corrections/{correction_id}"
                "/apply"
            ),
        )

        apply_response.raise_for_status()

        rerun = operation(
            client,
            (
                f"reviews/{review_case_id}"
                "/rerun"
            ),
        )

        rerun.raise_for_status()

        resolve = operation(
            client,
            (
                f"reviews/{review_case_id}"
                "/resolve"
            ),
            payload={
                "resolution": "APPROVE",
                "note": (
                    "Corrected values and rerun "
                    "controls support approval."
                ),
            },
        )

        resolve.raise_for_status()

        export_response = operation(
            client,
            (
                f"documents/{document_id}"
                "/exports"
            ),
            payload={
                "export_format": "JSON",
            },
        )

        export_response.raise_for_status()

        export_id = export_response.json()[
            "export"
        ]["id"]

        delivery_response = operation(
            client,
            (
                f"exports/{export_id}"
                "/notifications"
            ),
            payload={
                "channel": "EMAIL",
                "destination": (
                    "interactive-ui@example.test"
                ),
            },
        )

        delivery_response.raise_for_status()

        delivery_id = delivery_response.json()[
            "delivery"
        ]["id"]

        delivered = wait_for_delivery(
            client,
            delivery_id,
        )

        assert (
            delivered["delivery"]["status"]
            == "SUCCEEDED"
        )

        asyncio.run(
            force_delivery_failed(
                delivery_id
            )
        )

        retry = operation(
            client,
            (
                f"notifications/{delivery_id}"
                "/retry"
            ),
        )

        retry.raise_for_status()

        retried = wait_for_delivery(
            client,
            delivery_id,
        )

        assert (
            retried["delivery"]["status"]
            == "SUCCEEDED"
        )

        assert (
            retried["delivery"][
                "attempt_count"
            ] >= 2
        )

        refreshed_page = client.get(
            f"/documents/{document_id}"
        )

        refreshed_page.raise_for_status()

        assert "RESOLVED APPROVED" in (
            refreshed_page.text.upper()
        )

        logout = client.post(
            "/api/auth/logout"
        )

        logout.raise_for_status()

    print(
        {
            "status": "passed",
            "document_id": document_id,
            "review_case_id": (
                review_case_id
            ),
            "interactive_page_rendered": True,
            "invoice_sorting_and_pagination": (
                True
            ),
            "review_filters_and_pagination": (
                True
            ),
            "claim_completed": True,
            "note_added": True,
            "correction_proposed": True,
            "correction_applied": True,
            "controls_rerun": True,
            "review_resolved": True,
            "export_generated": True,
            "delivery_succeeded": True,
            "failed_delivery_retried": True,
            "audit_workspace_rendered": True,
            "elapsed_seconds": round(
                time.monotonic()
                - started_at,
                2,
            ),
        }
    )


if __name__ == "__main__":
    main()
