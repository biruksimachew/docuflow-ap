"use client";


type ApiErrorPayload = {
  detail?: {
    code?: string;
    message?: string;
  } | string;
  message?: string;
};


export class OperationRequestError extends Error {
  status: number;
  code: string | null;

  constructor(
    status: number,
    message: string,
    code: string | null = null,
  ) {
    super(message);
    this.name = "OperationRequestError";
    this.status = status;
    this.code = code;
  }
}


function errorMessage(
  payload: ApiErrorPayload | null,
  status: number,
): string {
  if (
    payload?.detail &&
    typeof payload.detail === "object" &&
    payload.detail.message
  ) {
    return payload.detail.message;
  }

  if (
    typeof payload?.detail === "string"
  ) {
    return payload.detail;
  }

  if (payload?.message) {
    return payload.message;
  }

  return (
    "The operation failed with status " +
    status +
    "."
  );
}


function errorCode(
  payload: ApiErrorPayload | null,
): string | null {
  if (
    payload?.detail &&
    typeof payload.detail === "object"
  ) {
    return payload.detail.code ?? null;
  }

  return null;
}


export async function operationRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const normalizedPath =
    path.replace(/^\/+/, "");

  const response = await fetch(
    `/api/operations/${normalizedPath}`,
    {
      ...init,
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(init.body
          ? {
              "Content-Type":
                "application/json",
            }
          : {}),
        ...(init.headers ?? {}),
      },
    },
  );

  if (response.status === 401) {
    window.location.assign(
      "/login?reason=session_expired",
    );

    throw new OperationRequestError(
      401,
      "Your session has expired.",
      "AUTHENTICATION_REQUIRED",
    );
  }

  const contentType =
    response.headers.get(
      "content-type",
    ) ?? "";

  const payload = contentType.includes(
    "application/json",
  )
    ? (
        await response.json()
      ) as ApiErrorPayload
    : null;

  if (!response.ok) {
    throw new OperationRequestError(
      response.status,
      errorMessage(
        payload,
        response.status,
      ),
      errorCode(payload),
    );
  }

  return payload as T;
}
