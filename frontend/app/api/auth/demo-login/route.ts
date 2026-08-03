import {
  SignJWT,
} from "jose";
import {
  NextResponse,
} from "next/server";

import {
  SESSION_COOKIE,
} from "@/lib/api";
import type {
  AppRole,
} from "@/lib/types";


const demoUsers: Record<
  AppRole,
  {
    sub: string;
    email: string;
  }
> = {
  AP_CLERK: {
    sub:
      "90000000-0000-0000-0000-000000000001",
    email:
      "clerk@docuflow.local",
  },
  REVIEWER: {
    sub:
      "90000000-0000-0000-0000-000000000002",
    email:
      "reviewer@docuflow.local",
  },
  ADMIN: {
    sub:
      "90000000-0000-0000-0000-000000000003",
    email:
      "admin@docuflow.local",
  },
};


export async function POST(
  request: Request,
) {
  const enabled =
    (
      process.env
        .DOCUFLOW_DEMO_AUTH_ENABLED ??
      "false"
    ).toLowerCase() === "true";

  if (!enabled) {
    return NextResponse.json(
      {
        message:
          "Demo authentication is disabled.",
      },
      {
        status: 403,
      },
    );
  }

  const body = (await request.json()) as {
    role?: AppRole;
  };

  const role = body.role;

  if (!role || !(role in demoUsers)) {
    return NextResponse.json(
      {
        message:
          "Choose a valid DocuFlow role.",
      },
      {
        status: 422,
      },
    );
  }

  const secret =
    process.env.SUPABASE_JWT_SECRET;

  if (!secret) {
    return NextResponse.json(
      {
        message:
          "Server-side JWT configuration is missing.",
      },
      {
        status: 503,
      },
    );
  }

  const user = demoUsers[role];
  const now = Math.floor(
    Date.now() / 1000,
  );

  const token = await new SignJWT({
    email: user.email,
    role: "authenticated",
  })
    .setProtectedHeader({
      alg: "HS256",
      typ: "JWT",
    })
    .setSubject(user.sub)
    .setAudience(
      process.env.AUTH_JWT_AUDIENCE ??
        "authenticated",
    )
    .setIssuedAt(now)
    .setExpirationTime(now + 3600)
    .sign(
      new TextEncoder().encode(secret),
    );

  const response = NextResponse.json({
    authenticated: true,
    role,
  });

  response.cookies.set(
    SESSION_COOKIE,
    token,
    {
      httpOnly: true,
      sameSite: "lax",
      secure:
        process.env.NODE_ENV ===
        "production",
      path: "/",
      maxAge: 3600,
    },
  );

  return response;
}
