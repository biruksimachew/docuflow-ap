export type SupabaseAuthUser = {
  id: string;
  email?: string;
};


export type SupabaseSession = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  expires_at?: number;
  token_type: string;
  user: SupabaseAuthUser;
};


export class SupabaseAuthError extends Error {
  status: number;

  constructor(
    status: number,
    message: string,
  ) {
    super(message);
    this.name = "SupabaseAuthError";
    this.status = status;
  }
}


function authConfiguration() {
  const baseUrl =
    process.env.SUPABASE_URL?.trim();

  const anonKey =
    process.env.SUPABASE_ANON_KEY?.trim();

  if (
    !baseUrl ||
    !anonKey ||
    anonKey.startsWith("replace")
  ) {
    throw new SupabaseAuthError(
      503,
      "Supabase authentication is not configured.",
    );
  }

  return {
    baseUrl: baseUrl.replace(/\/+$/, ""),
    anonKey,
  };
}


async function requestSession(
  grantType: "password" | "refresh_token",
  payload: Record<string, string>,
): Promise<SupabaseSession> {
  const {
    baseUrl,
    anonKey,
  } = authConfiguration();

  let response: Response;

  try {
    response = await fetch(
      (
        `${baseUrl}/auth/v1/token` +
        `?grant_type=${grantType}`
      ),
      {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type":
            "application/json",
          apikey: anonKey,
          Authorization:
            `Bearer ${anonKey}`,
        },
        body: JSON.stringify(payload),
      },
    );
  } catch {
    throw new SupabaseAuthError(
      503,
      "Supabase authentication is unavailable.",
    );
  }

  const body = await response
    .json()
    .catch(() => null) as
      | Partial<SupabaseSession>
      | null;

  if (
    !response.ok ||
    !body?.access_token ||
    !body.refresh_token ||
    !body.expires_in ||
    !body.user
  ) {
    throw new SupabaseAuthError(
      response.status,
      grantType === "password"
        ? "Email or password is incorrect."
        : "Your session has expired. Sign in again.",
    );
  }

  return body as SupabaseSession;
}


export async function signInWithPassword(
  email: string,
  password: string,
): Promise<SupabaseSession> {
  return requestSession(
    "password",
    {
      email,
      password,
    },
  );
}


export async function refreshSupabaseSession(
  refreshToken: string,
): Promise<SupabaseSession> {
  return requestSession(
    "refresh_token",
    {
      refresh_token: refreshToken,
    },
  );
}
