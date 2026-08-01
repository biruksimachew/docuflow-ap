from __future__ import annotations

import httpx

from scripts.auth_test_tokens import (
    authorization_headers,
    create_test_access_token,
)


BASE_URL = "http://127.0.0.1:8000"


def main() -> None:
    no_token = httpx.get(
        f"{BASE_URL}/api/v1/auth/me",
        timeout=20,
    )

    assert (
        no_token.status_code
        == 401
    )

    expired_token = (
        create_test_access_token(
            role="AP_CLERK",
            expires_in_seconds=-60,
        )
    )

    expired_response = httpx.get(
        f"{BASE_URL}/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {expired_token}"
            )
        },
        timeout=20,
    )

    assert (
        expired_response.status_code
        == 401
    )

    invalid_signature_token = (
        create_test_access_token(
            role="AP_CLERK",
            secret=(
                "different-secret-with-at-least-32-characters"
            ),
        )
    )

    invalid_signature_response = httpx.get(
        f"{BASE_URL}/api/v1/auth/me",
        headers={
            "Authorization": (
                "Bearer "
                + invalid_signature_token
            )
        },
        timeout=20,
    )

    assert (
        invalid_signature_response.status_code
        == 401
    )

    forged_claim_token = (
        create_test_access_token(
            role="AP_CLERK",
            extra_claims={
                "app_role": "ADMIN",
            },
        )
    )

    clerk_profile = httpx.get(
        f"{BASE_URL}/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {forged_claim_token}"
            )
        },
        timeout=20,
    )

    clerk_profile.raise_for_status()

    clerk_payload = (
        clerk_profile.json()
    )

    assert (
        clerk_payload["user"]["role"]
        == "AP_CLERK"
    )

    clerk_reviewer_check = httpx.get(
        (
            f"{BASE_URL}"
            "/api/v1/auth/reviewer-check"
        ),
        headers=authorization_headers(
            "AP_CLERK"
        ),
        timeout=20,
    )

    assert (
        clerk_reviewer_check.status_code
        == 403
    )

    reviewer_check = httpx.get(
        (
            f"{BASE_URL}"
            "/api/v1/auth/reviewer-check"
        ),
        headers=authorization_headers(
            "REVIEWER"
        ),
        timeout=20,
    )

    reviewer_check.raise_for_status()

    assert (
        reviewer_check.json()["role"]
        == "REVIEWER"
    )

    reviewer_admin_check = httpx.get(
        (
            f"{BASE_URL}"
            "/api/v1/auth/admin-check"
        ),
        headers=authorization_headers(
            "REVIEWER"
        ),
        timeout=20,
    )

    assert (
        reviewer_admin_check.status_code
        == 403
    )

    admin_check = httpx.get(
        (
            f"{BASE_URL}"
            "/api/v1/auth/admin-check"
        ),
        headers=authorization_headers(
            "ADMIN"
        ),
        timeout=20,
    )

    admin_check.raise_for_status()

    assert (
        admin_check.json()["role"]
        == "ADMIN"
    )

    protected_document_url = (
        f"{BASE_URL}/api/v1/documents/"
        "00000000-0000-0000-0000-000000000099"
        "/decision"
    )

    unprotected_attempt = httpx.get(
        protected_document_url,
        timeout=20,
    )

    assert (
        unprotected_attempt.status_code
        == 401
    )

    authenticated_attempt = httpx.get(
        protected_document_url,
        headers=authorization_headers(
            "AP_CLERK"
        ),
        timeout=20,
    )

    assert (
        authenticated_attempt.status_code
        == 404
    )

    events_response = httpx.get(
        (
            f"{BASE_URL}"
            "/api/v1/auth/security-events"
            "?limit=100"
        ),
        headers=authorization_headers(
            "ADMIN"
        ),
        timeout=20,
    )

    events_response.raise_for_status()

    events = events_response.json()[
        "events"
    ]

    event_types = {
        event["event_type"]
        for event in events
    }

    assert (
        "AUTHENTICATION_SUCCEEDED"
        in event_types
    )

    assert (
        "AUTHENTICATION_FAILED"
        in event_types
    )

    assert (
        "AUTHORIZATION_DENIED"
        in event_types
    )

    print(
        {
            "status": "passed",
            "jwt_signature_validation": True,
            "jwt_expiration_validation": True,
            "database_role_is_authoritative": True,
            "clerk_role": (
                clerk_payload[
                    "user"
                ]["role"]
            ),
            "reviewer_access": True,
            "admin_access": True,
            "clerk_denied_reviewer_access": True,
            "reviewer_denied_admin_access": True,
            "document_endpoints_protected": True,
            "security_audit_events_preserved": True,
            "audit_event_types": sorted(
                event_types
            ),
        }
    )


if __name__ == "__main__":
    main()