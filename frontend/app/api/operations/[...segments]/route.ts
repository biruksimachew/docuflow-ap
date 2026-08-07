import {
  cookies,
} from "next/headers";
import {
  NextRequest,
  NextResponse,
} from "next/server";

import {
  ACCESS_TOKEN_COOKIE,
} from "@/lib/session";


const INTERNAL_API_URL =
  process.env.DOCUFLOW_API_INTERNAL_URL ??
  "http://api:8000";

const ALLOWED_ROOTS = new Set([
  "reviews",
  "documents",
  "exports",
  "notifications",
  "dashboard",
]);


type RouteContext = {
  params: Promise<{
    segments: string[];
  }>;
};


function firstForwardedValue(
  value: string | null,
): string | null {
  if (!value) {
    return null;
  }

  return (
    value
      .split(",")[0]
      ?.trim() || null
  );
}


function sameOrigin(
  request: NextRequest,
): boolean {
  const origin = request.headers.get(
    "origin",
  );

  if (!origin) {
    return true;
  }

  const forwardedHost =
    firstForwardedValue(
      request.headers.get(
        "x-forwarded-host",
      ),
    );

  const host =
    forwardedHost ??
    request.headers.get("host");

  if (!host) {
    return false;
  }

  const forwardedProtocol =
    firstForwardedValue(
      request.headers.get(
        "x-forwarded-proto",
      ),
    );

  const protocol =
    forwardedProtocol ??
    request.nextUrl.protocol.replace(
      /:$/,
      "",
    );

  try {
    const originUrl = new URL(origin);

    return (
      originUrl.host === host &&
      originUrl.protocol ===
        `${protocol}:`
    );
  } catch {
    return false;
  }
}


async function forward(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  if (
    request.method !== "GET" &&
    !sameOrigin(request)
  ) {
    return NextResponse.json(
      {
        detail: {
          code: "CROSS_ORIGIN_ACTION_DENIED",
          message:
            "Operations actions must originate from this dashboard.",
        },
      },
      {
        status: 403,
      },
    );
  }

  const {
    segments,
  } = await context.params;

  const root = segments[0];

  if (
    !root ||
    !ALLOWED_ROOTS.has(root)
  ) {
    return NextResponse.json(
      {
        detail: {
          code: "OPERATION_NOT_ALLOWED",
          message:
            "The requested operations route is not allowed.",
        },
      },
      {
        status: 404,
      },
    );
  }

  const cookieStore = await cookies();

  const accessToken =
    cookieStore.get(
      ACCESS_TOKEN_COOKIE,
    )?.value;

  if (!accessToken) {
    return NextResponse.json(
      {
        detail: {
          code: "AUTHENTICATION_REQUIRED",
          message:
            "Sign in before performing this operation.",
        },
      },
      {
        status: 401,
      },
    );
  }

  const encodedPath = segments
    .map((segment) =>
      encodeURIComponent(segment),
    )
    .join("/");

  const backendUrl = new URL(
    `/api/v1/${encodedPath}`,
    INTERNAL_API_URL,
  );

  request.nextUrl.searchParams.forEach(
    (value, key) => {
      backendUrl.searchParams.append(
        key,
        value,
      );
    },
  );

  const requestHeaders = new Headers({
    Accept:
      request.headers.get("accept") ??
      "application/json",
    Authorization:
      `Bearer ${accessToken}`,
  });

  const contentType =
    request.headers.get(
      "content-type",
    );

  if (contentType) {
    requestHeaders.set(
      "Content-Type",
      contentType,
    );
  }

  const hasBody =
    !["GET", "HEAD"].includes(
      request.method,
    );

  const backendResponse = await fetch(
    backendUrl,
    {
      method: request.method,
      cache: "no-store",
      headers: requestHeaders,
      body: hasBody
        ? await request.arrayBuffer()
        : undefined,
    },
  );

  const responseHeaders = new Headers();

  for (const name of [
    "content-type",
    "content-disposition",
    "x-content-sha256",
  ]) {
    const value =
      backendResponse.headers.get(
        name,
      );

    if (value) {
      responseHeaders.set(
        name,
        value,
      );
    }
  }

  return new Response(
    await backendResponse.arrayBuffer(),
    {
      status: backendResponse.status,
      headers: responseHeaders,
    },
  );
}


export async function GET(
  request: NextRequest,
  context: RouteContext,
) {
  return forward(
    request,
    context,
  );
}


export async function POST(
  request: NextRequest,
  context: RouteContext,
) {
  return forward(
    request,
    context,
  );
}
