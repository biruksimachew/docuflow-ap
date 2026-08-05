import {
  decodeJwt,
} from "jose";


export const ACCESS_TOKEN_COOKIE =
  "docuflow_access_token";

export const REFRESH_TOKEN_COOKIE =
  "docuflow_refresh_token";

export const SESSION_SOURCE_COOKIE =
  "docuflow_session_source";

export type SessionSource =
  | "supabase"
  | "demo";


const isSecureCookie =
  process.env.NODE_ENV === "production";


export function accessCookieOptions(
  maxAge: number,
) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: isSecureCookie,
    path: "/",
    maxAge,
  };
}


export function refreshCookieOptions(
  maxAge = 60 * 60 * 24 * 30,
) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: isSecureCookie,
    path: "/",
    maxAge,
  };
}


export function sourceCookieOptions(
  maxAge: number,
) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: isSecureCookie,
    path: "/",
    maxAge,
  };
}


export function tokenExpiresSoon(
  token: string,
): boolean {
  try {
    const claims = decodeJwt(token);
    const expiresAt = claims.exp;

    if (
      typeof expiresAt !== "number"
    ) {
      return true;
    }

    const refreshWindow = Number(
      process.env
        .DOCUFLOW_SESSION_REFRESH_WINDOW_SECONDS ??
        "60",
    );

    const now = Math.floor(
      Date.now() / 1000,
    );

    return (
      expiresAt <=
      now +
        (
          Number.isFinite(refreshWindow)
            ? Math.max(refreshWindow, 0)
            : 60
        )
    );
  } catch {
    return true;
  }
}
