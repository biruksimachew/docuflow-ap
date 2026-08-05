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
} from "@/lib/session";


export async function POST() {
  const response = new NextResponse(
    null,
    {
      status: 303,
      headers: {
        Location: "/login",
      },
    },
  );

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

  response.headers.set(
    "Cache-Control",
    "no-store",
  );

  return response;
}
