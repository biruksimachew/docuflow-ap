import Link from "next/link";

import { InvoiceTable } from "@/components/invoice-table";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import { docuFlowFetch } from "@/lib/api";
import type {
  DashboardOverview,
} from "@/lib/types";


export const metadata = {
  title: "Operations overview",
};


export default async function DashboardPage() {
  const overview =
    await docuFlowFetch<DashboardOverview>(
      "/api/v1/dashboard/overview",
    );

  const metrics = overview.metrics;

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            Operations overview
          </div>
          <h1>
            Invoice control center
          </h1>
          <p>
            A live view of processing outcomes,
            review pressure and downstream
            delivery health.
          </p>
        </div>

        <Link
          className="secondary-button"
          href="/invoices"
        >
          Open invoice queue
        </Link>
      </section>

      <section className="metrics-grid">
        <MetricCard
          eyebrow="Total invoices"
          value={metrics.total_documents}
          detail="All documents received by DocuFlow."
        />
        <MetricCard
          eyebrow="Auto-approved"
          value={metrics.auto_approved}
          detail={`${metrics.approval_rate}% straight-through rate`}
          tone="accent"
        />
        <MetricCard
          eyebrow="Needs review"
          value={metrics.review_required}
          detail={`${metrics.open_reviews} unclaimed · ${metrics.claimed_reviews} claimed`}
          tone="warning"
        />
        <MetricCard
          eyebrow="Ready exports"
          value={metrics.ready_exports}
          detail={`${metrics.notifications_in_flight} deliveries in flight`}
        />
      </section>

      <section className="content-grid">
        <article className="panel panel-wide">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">
                Recent activity
              </div>
              <h2>Latest invoices</h2>
            </div>
            <Link
              className="text-link"
              href="/invoices"
            >
              View all
            </Link>
          </div>

          <InvoiceTable
            documents={
              overview.recent_documents
            }
            compact
          />
        </article>

        <aside className="panel health-panel">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">
                Control health
              </div>
              <h2>Exception signals</h2>
            </div>
          </div>

          <div className="health-list">
            <div className="health-row">
              <div>
                <div className="health-label">
                  Review queue
                </div>
                <div className="health-copy">
                  Human decisions pending
                </div>
              </div>
              <StatusBadge
                value={
                  metrics.review_required > 0
                    ? "REVIEW_REQUIRED"
                    : "CLEAR"
                }
              />
            </div>

            <div className="health-row">
              <div>
                <div className="health-label">
                  Rejected invoices
                </div>
                <div className="health-copy">
                  Deterministic or manual
                </div>
              </div>
              <strong>
                {metrics.rejected}
              </strong>
            </div>

            <div className="health-row">
              <div>
                <div className="health-label">
                  Processing failures
                </div>
                <div className="health-copy">
                  Technical intervention
                </div>
              </div>
              <strong>
                {metrics.failed}
              </strong>
            </div>

            <div className="health-row">
              <div>
                <div className="health-label">
                  Delivery failures
                </div>
                <div className="health-copy">
                  Webhook or email
                </div>
              </div>
              <strong>
                {metrics.notification_failures}
              </strong>
            </div>
          </div>

          <div className="health-footer">
            <span className="live-dot" />
            Backed by live API and database state
          </div>
        </aside>
      </section>
    </div>
  );
}
