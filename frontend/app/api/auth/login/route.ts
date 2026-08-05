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
import {
  SupabaseAuthError,
  signInWithPassword,
} from "@/lib/supabase-auth";


type LoginPayload = {
  email?: unknown;
  password?: unknown;
};


export async function POST(
  request: Request,
) {
  let body: LoginPayload;

  try {
    body =
      await request.json() as LoginPayload;
  } catch {
    return NextResponse.json(
      {
        message:
          "Enter an email address and password.",
      },
      {
        status: 400,
      },
    );
  }

  const email =
    typeof body.email === "string"
      ? body.email.trim().toLowerCase()
      : "";

  const password =
    typeof body.password === "string"
      ? body.password
      : "";

  if (
    !email.includes("@") ||
    password.length < 8
  ) {
    return NextResponse.json(
      {
        message:
          "Enter a valid email address and password.",
      },
      {
        status: 422,
      },
    );
  }

  try {
    const session =
      await signInWithPassword(
        email,
        password,
      );

    const response =
      NextResponse.json(
        {
          authenticated: true,
          user: {
            id: session.user.id,
            email:
              session.user.email ??
              email,
          },
        },
      );

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

    response.headers.set(
      "Cache-Control",
      "no-store",
    );

    return response;
  } catch (error) {
    if (
      error instanceof
      SupabaseAuthError
    ) {
      return NextResponse.json(
        {
          message: error.message,
        },
        {
          status:
            error.status >= 500
              ? 503
              : 401,
        },
      );
    }

    return NextResponse.json(
      {
        message:
          "Sign-in could not be completed.",
      },
      {
        status: 500,
      },
    );
  }
}
