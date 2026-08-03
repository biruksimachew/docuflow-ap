import { redirect } from "next/navigation";

import { LoginForm } from "@/components/login-form";
import { getAccessToken } from "@/lib/api";


export const metadata = {
  title: "Sign in",
};


export default async function LoginPage() {
  const token = await getAccessToken();

  if (token) {
    redirect("/dashboard");
  }

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
        <div className="login-card">
          <div className="eyebrow">
            Portfolio environment
          </div>
          <h2>Choose a demo role</h2>
          <p className="login-intro">
            Each role is backed by the same
            database-authoritative RBAC model
            used by the API.
          </p>

          <LoginForm />
        </div>
      </section>
    </main>
  );
}
