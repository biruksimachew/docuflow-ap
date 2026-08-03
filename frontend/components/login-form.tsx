"use client";

import {
  useState,
  type FormEvent,
} from "react";
import { useRouter } from "next/navigation";

import type { AppRole } from "@/lib/types";


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


export function LoginForm() {
  const router = useRouter();

  const [role, setRole] =
    useState<AppRole>("ADMIN");
  const [loading, setLoading] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);

  async function submit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();
    setLoading(true);
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

      if (!response.ok) {
        const payload = await response.json();

        throw new Error(
          payload.message ??
            "Demo sign-in failed.",
        );
      }

      router.push("/dashboard");
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Demo sign-in failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      className="login-form"
      onSubmit={submit}
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
              checked={role === option.value}
              onChange={() =>
                setRole(option.value)
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

      {error && (
        <div className="form-error">
          {error}
        </div>
      )}

      <button
        className="primary-button"
        type="submit"
        disabled={loading}
      >
        {loading
          ? "Opening workspace…"
          : "Enter operations workspace"}
      </button>

      <p className="login-note">
        Local demo authentication. Credentials
        remain server-side and are never exposed
        to the browser.
      </p>
    </form>
  );
}
