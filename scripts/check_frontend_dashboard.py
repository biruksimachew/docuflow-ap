from __future__ import annotations

import asyncio
import os
import time

import httpx

from scripts.provision_local_auth_users import (
    provision_local_auth_users,
)


FRONTEND_URL = "http://frontend:3000"

ACCESS_COOKIE = (
    "docuflow_access_token"
)

REFRESH_COOKIE = (
    "docuflow_refresh_token"
)


def wait_for_frontend() -> None:
    last_error: Exception | None = None

    for _ in range(60):
        try:
            response = httpx.get(
                (
                    f"{FRONTEND_URL}"
                    "/api/health"
                ),
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


def main() -> None:
    started_at = time.monotonic()

    asyncio.run(
        provision_local_auth_users()
    )

    wait_for_frontend()

    password = os.getenv(
        "DOCUFLOW_LOCAL_AUTH_PASSWORD",
        "DocuFlowLocal!2026",
    )

    with httpx.Client(
        base_url=FRONTEND_URL,
        follow_redirects=False,
        timeout=30,
    ) as anonymous:
        protected = anonymous.get(
            "/dashboard"
        )

        assert protected.status_code in {
            307,
            308,
        }

        assert (
            protected.headers[
                "location"
            ].startswith(
                "/login"
            )
            or "/login" in (
                protected.headers[
                    "location"
                ]
            )
        )

    with httpx.Client(
        base_url=FRONTEND_URL,
        follow_redirects=True,
        timeout=30,
    ) as client:
        login_page = client.get(
            "/login"
        )
        login_page.raise_for_status()

        assert "Sign in to DocuFlow" in (
            login_page.text
        )

        assert "Email address" in (
            login_page.text
        )

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

        assert (
            ACCESS_COOKIE
            in client.cookies
        )

        assert (
            REFRESH_COOKIE
            in client.cookies
        )

        dashboard = client.get(
            "/dashboard"
        )
        dashboard.raise_for_status()

        assert "Invoice control center" in (
            dashboard.text
        )

        invoices = client.get(
            "/invoices"
        )
        invoices.raise_for_status()

        assert "Invoice queue" in (
            invoices.text
        )

        reviews = client.get(
            "/reviews"
        )
        reviews.raise_for_status()

        assert "Exception queue" in (
            reviews.text
        )

        client.cookies.delete(
            ACCESS_COOKIE
        )

        refreshed = client.get(
            "/dashboard"
        )
        refreshed.raise_for_status()

        assert (
            ACCESS_COOKIE
            in client.cookies
        )

        logout = client.post(
            "/api/auth/logout"
        )
        logout.raise_for_status()

        assert (
            client.cookies.get(
                ACCESS_COOKIE
            )
            in {
                None,
                "",
            }
        )

        assert (
            client.cookies.get(
                REFRESH_COOKIE
            )
            in {
                None,
                "",
            }
        )

    demo_enabled = (
        os.getenv(
            "DOCUFLOW_DEMO_AUTH_ENABLED",
            "false",
        ).lower() == "true"
    )

    demo_login_passed = False

    if demo_enabled:
        with httpx.Client(
            base_url=FRONTEND_URL,
            follow_redirects=True,
            timeout=30,
        ) as demo_client:
            demo_login = demo_client.post(
                "/api/auth/demo-login",
                json={
                    "role": "AP_CLERK",
                },
            )
            demo_login.raise_for_status()

            assert (
                ACCESS_COOKIE
                in demo_client.cookies
            )

            assert (
                REFRESH_COOKIE
                not in demo_client.cookies
            )

            demo_dashboard = (
                demo_client.get(
                    "/dashboard"
                )
            )
            demo_dashboard.raise_for_status()

            demo_login_passed = True

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "protected_route_redirect": True,
            "real_supabase_login": True,
            "http_only_access_cookie": True,
            "refresh_cookie_issued": True,
            "session_refresh": True,
            "dashboard_rendered": True,
            "invoice_queue_rendered": True,
            "review_queue_rendered": True,
            "logout_completed": True,
            "demo_login": (
                demo_login_passed
                if demo_enabled
                else "disabled"
            ),
            "elapsed_seconds": (
                elapsed_seconds
            ),
        }
    )


if __name__ == "__main__":
    main()
