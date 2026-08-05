import {
  cookies,
} from "next/headers";
import {
  redirect,
} from "next/navigation";

import {
  ACCESS_TOKEN_COOKIE,
} from "@/lib/session";
import type {
  AuthenticatedProfile,
} from "@/lib/types";


export const SESSION_COOKIE =
  ACCESS_TOKEN_COOKIE;

const INTERNAL_API_URL =
  process.env.DOCUFLOW_API_INTERNAL_URL ??
  "http://api:8000";


export class DocuFlowApiError extends Error {
  status: number;
  payload: unknown;

  constructor(
    status: number,
    payload: unknown,
  ) {
    super(
      `DocuFlow API request failed with ${status}.`,
    );
    this.name = "DocuFlowApiError";
    this.status = status;
    this.payload = payload;
  }
}


export async function getAccessToken():
Promise<string | null> {
  const cookieStore = await cookies();

  return (
    cookieStore.get(
      ACCESS_TOKEN_COOKIE,
    )?.value ?? null
  );
}


export async function docuFlowFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = await getAccessToken();

  if (!token) {
    redirect(
      "/login?reason=authentication_required",
    );
  }

  const response = await fetch(
    `${INTERNAL_API_URL}${path}`,
    {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    },
  );

  if (response.status === 401) {
    redirect(
      "/login?reason=session_expired",
    );
  }

  if (response.status === 403) {
    redirect(
      "/dashboard?reason=access_denied",
    );
  }

  if (!response.ok) {
    let payload: unknown = null;

    try {
      payload = await response.json();
    } catch {
      payload = await response.text();
    }

    throw new DocuFlowApiError(
      response.status,
      payload,
    );
  }

  return response.json() as Promise<T>;
}


export async function requireProfile():
Promise<AuthenticatedProfile> {
  return docuFlowFetch<AuthenticatedProfile>(
    "/api/v1/auth/me",
  );
}
