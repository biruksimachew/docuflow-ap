import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import { docuFlowFetch, requireProfile } from "@/lib/api";
import {
  formatDateTime,
  formatMoney,
} from "@/lib/format";
import type {
  ReviewListResponse,
} from "@/lib/types";


export const metadata = {
  title: "Review queue",
};


export default async function ReviewsPage() {
  const profile = await requireProfile();

  if (profile.user.role === "AP_CLERK") {
    return (
      <div className="page-stack">
        <section className="page-heading">
          <div>
            <div className="eyebrow">
              Human review
            </div>
            <h1>Review queue</h1>
          </div>
        </section>

        <section className="access-panel">
          <div className="access-icon">
            !
          </div>
          <h2>Reviewer access required</h2>
          <p>
            AP clerks can monitor document
            status, but only reviewers and
            administrators can open the human
            review queue.
          </p>
        </section>
      </div>
    );
  }

  const result =
    await docuFlowFetch<ReviewListResponse>(
      "/api/v1/dashboard/reviews?limit=100",
    );

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            Human review
          </div>
          <h1>Exception queue</h1>
          <p>
            High-priority exceptions appear
            first, followed by the oldest
            unresolved cases.
          </p>
        </div>

        <div className="result-count">
          {result.pagination.total}
          <span>cases</span>
        </div>
      </section>

      <section className="review-grid">
        {result.reviews.length === 0 ? (
          <div className="panel empty-state">
            <div className="empty-icon">
              ✓
            </div>
            <h3>Review queue is clear</h3>
            <p>
              No invoices currently require
              human resolution.
            </p>
          </div>
        ) : (
          result.reviews.map((review) => (
            <article
              key={review.id}
              className="review-card"
            >
              <div className="review-card-top">
                <div>
                  <div className="review-vendor">
                    {review.vendor_name ??
                      "Unresolved vendor"}
                  </div>
                  <div className="review-invoice">
                    {review.invoice_number ??
                      review.original_filename}
                  </div>
                </div>
                <StatusBadge
                  value={review.status}
                />
              </div>

              <p className="review-explanation">
                {review.explanation}
              </p>

              <div className="reason-list">
                {review.reason_codes.map(
                  (reason) => (
                    <span key={reason}>
                      {reason}
                    </span>
                  ),
                )}
              </div>

              <div className="review-meta">
                <div>
                  <span>Amount</span>
                  <strong>
                    {formatMoney(
                      review.total_amount,
                      review.currency,
                    )}
                  </strong>
                </div>
                <div>
                  <span>Created</span>
                  <strong>
                    {formatDateTime(
                      review.created_at,
                    )}
                  </strong>
                </div>
              </div>

              <Link
                className="card-link"
                href={`/documents/${review.document_id}`}
              >
                Open review workspace
                <span>→</span>
              </Link>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
