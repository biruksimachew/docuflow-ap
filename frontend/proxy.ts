import type {
  NextRequest,
} from "next/server";
import {
  NextResponse,
} from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
  REFRESH_TOKEN_COOKIE,
  SESSION_SOURCE_COOKIE,
  accessCookieOptions,
  refreshCookieOptions,
  sourceCookieOptions,
  tokenExpiresSoon,
} from "@/lib/session";
import {
  refreshSupabaseSession,
} from "@/lib/supabase-auth";


const protectedPrefixes = [
  "/dashboard",
  "/invoices",
  "/reviews",
  "/documents",
];


function isProtectedPath(
  pathname: string,
): boolean {
  return protectedPrefixes.some(
    (prefix) =>
      pathname === prefix ||
      pathname.startsWith(
        `${prefix}/`,
      ),
  );
}


function clearSession(
  response: NextResponse,
): NextResponse {
  response.cookies.set(
    ACCESS_TOKEN_COOKIE,
    "",
    accessCookieOptions(0),
  );
  response.cookies.set(
    REFRESH_TOKEN_COOKIE,
    "",
    refreshCookieOptions(0),
  );
  response.cookies.set(
    SESSION_SOURCE_COOKIE,
    "",
    sourceCookieOptions(0),
  );

  return response;
}


function setSupabaseSession(
  response: NextResponse,
  session: {
    access_token: string;
    refresh_token: string;
    expires_in: number;
  },
): NextResponse {
  response.cookies.set(
    ACCESS_TOKEN_COOKIE,
    session.access_token,
    accessCookieOptions(
      session.expires_in,
    ),
  );
  response.cookies.set(
    REFRESH_TOKEN_COOKIE,
    session.refresh_token,
    refreshCookieOptions(),
  );
  response.cookies.set(
    SESSION_SOURCE_COOKIE,
    "supabase",
    sourceCookieOptions(
      session.expires_in,
    ),
  );

  return response;
}


function loginUrl(
  request: NextRequest,
  reason: string,
): URL {
  const url =
    request.nextUrl.clone();

  url.pathname = "/login";
  url.search = "";

  url.searchParams.set(
    "reason",
    reason,
  );

  const returnPath =
    request.nextUrl.pathname +
    request.nextUrl.search;

  if (
    returnPath.startsWith("/") &&
    !returnPath.startsWith("//")
  ) {
    url.searchParams.set(
      "next",
      returnPath,
    );
  }

  return url;
}


export async function proxy(
  request: NextRequest,
) {
  const pathname =
    request.nextUrl.pathname;

  const protectedPath =
    isProtectedPath(pathname);

  const loginPath =
    pathname === "/login";

  const loginReason =
    request.nextUrl.searchParams.get(
      "reason",
    );

  const accessToken =
    request.cookies.get(
      ACCESS_TOKEN_COOKIE,
    )?.value;

  const refreshToken =
    request.cookies.get(
      REFRESH_TOKEN_COOKIE,
    )?.value;

  /*
   * A protected Server Component redirects here after FastAPI rejects
   * the access token. Clear the rejected session before rendering the
   * login page so Proxy cannot bounce the request back to /dashboard.
   */
  if (
    loginPath &&
    (
      loginReason ===
        "session_expired" ||
      loginReason ===
        "authentication_required"
    )
  ) {
    return clearSession(
      NextResponse.next(),
    );
  }

  if (
    accessToken &&
    !tokenExpiresSoon(accessToken)
  ) {
    if (loginPath) {
      const dashboardUrl =
        request.nextUrl.clone();

      dashboardUrl.pathname =
        "/dashboard";
      dashboardUrl.search = "";

      return NextResponse.redirect(
        dashboardUrl,
      );
    }

    return NextResponse.next();
  }

  if (refreshToken) {
    try {
      const session =
        await refreshSupabaseSession(
          refreshToken,
        );

      const target =
        request.nextUrl.clone();

      if (loginPath) {
        target.pathname =
          "/dashboard";
        target.search = "";
      }

      return setSupabaseSession(
        NextResponse.redirect(
          target,
        ),
        session,
      );
    } catch {
      if (protectedPath) {
        return clearSession(
          NextResponse.redirect(
            loginUrl(
              request,
              "session_expired",
            ),
          ),
        );
      }

      return clearSession(
        NextResponse.next(),
      );
    }
  }

  if (protectedPath) {
    return clearSession(
      NextResponse.redirect(
        loginUrl(
          request,
          accessToken
            ? "session_expired"
            : "authentication_required",
        ),
      ),
    );
  }

  if (
    loginPath &&
    accessToken
  ) {
    return clearSession(
      NextResponse.next(),
    );
  }

  return NextResponse.next();
}


export const config = {
  matcher: [
    "/dashboard/:path*",
    "/invoices/:path*",
    "/reviews/:path*",
    "/documents/:path*",
    "/login",
  ],
};
