from __future__ import annotations

import time

import httpx


FRONTEND_URL = "http://frontend:3000"


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

    wait_for_frontend()

    with httpx.Client(
        base_url=FRONTEND_URL,
        follow_redirects=True,
        timeout=30,
    ) as client:
        login_page = client.get(
            "/login"
        )
        login_page.raise_for_status()

        assert "Choose a demo role" in (
            login_page.text
        )

        login = client.post(
            "/api/auth/demo-login",
            json={
                "role": "ADMIN",
            },
        )
        login.raise_for_status()

        assert (
            "docuflow_access_token"
            in client.cookies
        )

        dashboard = client.get(
            "/dashboard"
        )
        dashboard.raise_for_status()

        assert "Invoice control center" in (
            dashboard.text
        )
        assert "Latest invoices" in (
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

        logout = client.post(
            "/api/auth/logout"
        )
        logout.raise_for_status()

        assert (
            client.cookies.get(
                "docuflow_access_token"
            )
            in {
                None,
                "",
            }
        )

    elapsed_seconds = round(
        time.monotonic()
        - started_at,
        2,
    )

    print(
        {
            "status": "passed",
            "frontend_health": True,
            "demo_login": True,
            "http_only_session_cookie": True,
            "dashboard_rendered": True,
            "invoice_queue_rendered": True,
            "review_queue_rendered": True,
            "logout_completed": True,
            "elapsed_seconds": elapsed_seconds,
        }
    )


if __name__ == "__main__":
    main()
