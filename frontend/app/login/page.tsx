import {
  LoginForm,
} from "@/components/login-form";


export const metadata = {
  title: "Sign in",
};


type LoginPageProps = {
  searchParams: Promise<{
    reason?: string;
  }>;
};


const reasonMessages: Record<
  string,
  string
> = {
  authentication_required:
    "Sign in to open the operations workspace.",
  session_expired:
    "Your session expired. Sign in again.",
};


export default async function LoginPage({
  searchParams,
}: LoginPageProps) {
  const params = await searchParams;

  const demoEnabled =
    (
      process.env
        .DOCUFLOW_DEMO_AUTH_ENABLED ??
      "false"
    ).toLowerCase() === "true";

  const localEnvironment =
    (
      process.env.APP_ENV ??
      "local"
    ).toLowerCase() === "local";

  const notice =
    params.reason
      ? reasonMessages[
          params.reason
        ]
      : null;

  return (
    <main className="login-page">
      <section className="login-visual">
        <div className="login-brand">
          <div className="brand-mark brand-mark-large">
            D
          </div>
          <div>
            <div className="brand-name brand-name-light">
              DocuFlow
            </div>
            <div className="brand-subtitle brand-subtitle-light">
              AP Operations
            </div>
          </div>
        </div>

        <div className="visual-copy">
          <div className="eyebrow eyebrow-light">
            Invoice intelligence
          </div>
          <h1>
            From intake to approval,
            every control stays visible.
          </h1>
          <p>
            Monitor extraction, validation,
            matching, review, exports and
            delivery evidence from one
            operational workspace.
          </p>
        </div>

        <div className="visual-flow">
          <div className="flow-step">
            <span>01</span>
            Secure intake
          </div>
          <div className="flow-line" />
          <div className="flow-step">
            <span>02</span>
            Deterministic controls
          </div>
          <div className="flow-line" />
          <div className="flow-step">
            <span>03</span>
            Audited resolution
          </div>
        </div>
      </section>

      <section className="login-panel">
        <div className="login-card login-card-wide">
          <div className="eyebrow">
            Secure operations access
          </div>
          <h2>Sign in to DocuFlow</h2>
          <p className="login-intro">
            Supabase authenticates the user.
            The API then resolves the
            database-authoritative DocuFlow
            role for every protected request.
          </p>

          {notice && (
            <div
              className="login-notice"
              role="status"
            >
              {notice}
            </div>
          )}

          <LoginForm
            demoEnabled={demoEnabled}
            localEnvironment={
              localEnvironment
            }
          />
        </div>
      </section>
    </main>
  );
}
