"use client";

import {
  useState,
  type FormEvent,
} from "react";
import {
  useRouter,
  useSearchParams,
} from "next/navigation";

import type {
  AppRole,
} from "@/lib/types";


const roles: Array<{
  value: AppRole;
  label: string;
  description: string;
  initials: string;
}> = [
  {
    value: "AP_CLERK",
    label: "AP Clerk",
    description:
      "Monitor invoices, evidence and accounting exports.",
    initials: "AC",
  },
  {
    value: "REVIEWER",
    label: "Reviewer",
    description:
      "Claim exceptions and resolve review cases.",
    initials: "RV",
  },
  {
    value: "ADMIN",
    label: "Administrator",
    description:
      "See the complete operational and audit workspace.",
    initials: "AD",
  },
];


const localAccounts = [
  {
    label: "AP Clerk",
    email:
      "ap.clerk@docuflow.local",
  },
  {
    label: "Reviewer",
    email:
      "reviewer.user@docuflow.local",
  },
  {
    label: "Administrator",
    email:
      "administrator@docuflow.local",
  },
];


function safeNextPath(
  value: string | null,
): string {
  if (
    value &&
    value.startsWith("/") &&
    !value.startsWith("//")
  ) {
    return value;
  }

  return "/dashboard";
}


export function LoginForm({
  demoEnabled,
  localEnvironment,
}: {
  demoEnabled: boolean;
  localEnvironment: boolean;
}) {
  const router = useRouter();
  const searchParams =
    useSearchParams();

  const [email, setEmail] =
    useState(
      "administrator@docuflow.local",
    );
  const [password, setPassword] =
    useState("");
  const [role, setRole] =
    useState<AppRole>("ADMIN");
  const [loadingMode, setLoadingMode] =
    useState<
      "credentials" | "demo" | null
    >(null);
  const [error, setError] =
    useState<string | null>(null);

  const nextPath = safeNextPath(
    searchParams.get("next"),
  );

  async function submitCredentials(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setLoadingMode("credentials");
    setError(null);

    try {
      const response = await fetch(
        "/api/auth/login",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            email,
            password,
          }),
        },
      );

      const payload = await response
        .json()
        .catch(() => null) as
          | {
              message?: string;
            }
          | null;

      if (!response.ok) {
        throw new Error(
          payload?.message ??
            "Sign-in failed.",
        );
      }

      router.push(nextPath);
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Sign-in failed.",
      );
    } finally {
      setLoadingMode(null);
    }
  }

  async function submitDemo(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setLoadingMode("demo");
    setError(null);

    try {
      const response = await fetch(
        "/api/auth/demo-login",
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            role,
          }),
        },
      );

      const payload = await response
        .json()
        .catch(() => null) as
          | {
              message?: string;
            }
          | null;

      if (!response.ok) {
        throw new Error(
          payload?.message ??
            "Demo sign-in failed.",
        );
      }

      router.push(nextPath);
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Demo sign-in failed.",
      );
    } finally {
      setLoadingMode(null);
    }
  }

  return (
    <div className="login-form-stack">
      <form
        className="login-form"
        onSubmit={submitCredentials}
      >
        <div className="credential-fields">
          <label className="credential-field">
            <span>Email address</span>
            <input
              type="email"
              name="email"
              autoComplete="username"
              value={email}
              onChange={(event) =>
                setEmail(
                  event.target.value,
                )
              }
              required
            />
          </label>

          <label className="credential-field">
            <span>Password</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) =>
                setPassword(
                  event.target.value,
                )
              }
              minLength={8}
              required
            />
          </label>
        </div>

        {localEnvironment && (
          <div className="local-account-picker">
            <span>Local accounts</span>
            <div>
              {localAccounts.map(
                (account) => (
                  <button
                    key={account.email}
                    type="button"
                    onClick={() =>
                      setEmail(
                        account.email,
                      )
                    }
                  >
                    {account.label}
                  </button>
                ),
              )}
            </div>
          </div>
        )}

        {error && (
          <div
            className="form-error"
            role="alert"
          >
            {error}
          </div>
        )}

        <button
          className="primary-button"
          type="submit"
          disabled={
            loadingMode !== null
          }
        >
          {loadingMode ===
          "credentials"
            ? "Signing in…"
            : "Sign in securely"}
        </button>

        <p className="login-note">
          Credentials are exchanged by the
          server and stored only in HTTP-only
          session cookies.
        </p>
      </form>

      {demoEnabled && (
        <>
          <div className="login-divider">
            <span>
              Portfolio demo access
            </span>
          </div>

          <form
            className="login-form"
            onSubmit={submitDemo}
          >
            <div className="role-options">
              {roles.map((option) => (
                <label
                  key={option.value}
                  className={
                    role === option.value
                      ? "role-option role-option-active"
                      : "role-option"
                  }
                >
                  <input
                    type="radio"
                    name="role"
                    value={option.value}
                    checked={
                      role === option.value
                    }
                    onChange={() =>
                      setRole(
                        option.value,
                      )
                    }
                  />
                  <span className="role-avatar">
                    {option.initials}
                  </span>
                  <span className="role-text">
                    <span className="role-label">
                      {option.label}
                    </span>
                    <span className="role-description">
                      {option.description}
                    </span>
                  </span>
                  <span className="role-check">
                    ✓
                  </span>
                </label>
              ))}
            </div>

            <button
              className="secondary-button full-width-button"
              type="submit"
              disabled={
                loadingMode !== null
              }
            >
              {loadingMode === "demo"
                ? "Opening demo…"
                : "Continue with demo role"}
            </button>
          </form>
        </>
      )}
    </div>
  );
}
