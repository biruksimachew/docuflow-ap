import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import { docuFlowFetch } from "@/lib/api";
import {
  formatDate,
  formatDateTime,
  formatMoney,
  humanize,
} from "@/lib/format";
import type {
  DocumentDetailResponse,
} from "@/lib/types";


type DocumentPageProps = {
  params: Promise<{
    documentId: string;
  }>;
};


export const metadata = {
  title: "Invoice detail",
};


export default async function DocumentPage({
  params,
}: DocumentPageProps) {
  const { documentId } = await params;

  const detail =
    await docuFlowFetch<DocumentDetailResponse>(
      `/api/v1/dashboard/documents/${documentId}`,
    );

  const document = detail.document;

  return (
    <div className="page-stack">
      <section className="detail-heading">
        <div>
          <Link
            className="back-link"
            href="/invoices"
          >
            ← Back to invoices
          </Link>
          <div className="eyebrow">
            Invoice workspace
          </div>
          <h1>
            {document.invoice_number ??
              "Pending invoice number"}
          </h1>
          <p>
            {document.vendor_name ??
              "Vendor identity unresolved"}
            <span className="heading-separator">
              ·
            </span>
            {document.original_filename}
          </p>
        </div>

        <div className="detail-status">
          <StatusBadge
            value={document.status}
          />
          <div className="detail-amount">
            {formatMoney(
              document.total_amount,
              document.currency,
            )}
          </div>
        </div>
      </section>

      <section className="detail-grid">
        <article className="panel detail-main">
          <div className="panel-header">
            <div>
              <div className="panel-kicker">
                Extracted invoice
              </div>
              <h2>Header information</h2>
            </div>
          </div>

          <dl className="detail-list">
            <div>
              <dt>Vendor</dt>
              <dd>
                {document.vendor_name ?? "—"}
              </dd>
            </div>
            <div>
              <dt>Invoice number</dt>
              <dd>
                {document.invoice_number ?? "—"}
              </dd>
            </div>
            <div>
              <dt>Invoice date</dt>
              <dd>
                {formatDate(
                  document.invoice_date,
                )}
              </dd>
            </div>
            <div>
              <dt>Due date</dt>
              <dd>
                {formatDate(
                  document.due_date,
                )}
              </dd>
            </div>
            <div>
              <dt>Purchase order</dt>
              <dd>
                {document.purchase_order_number ??
                  "Not provided"}
              </dd>
            </div>
            <div>
              <dt>Resolution source</dt>
              <dd>
                {humanize(
                  document.final_resolution_source,
                )}
              </dd>
            </div>
          </dl>

          <div className="line-section">
            <div className="panel-header">
              <div>
                <div className="panel-kicker">
                  Line extraction
                </div>
                <h2>
                  {detail.line_items.length}
                  {" "}
                  line items
                </h2>
              </div>
            </div>

            <div className="table-shell">
              <table className="data-table line-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Description</th>
                    <th>Qty</th>
                    <th>Unit price</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.line_items.map(
                    (line) => (
                      <tr key={line.id}>
                        <td>{line.line_number}</td>
                        <td>
                          <div className="primary-cell">
                            {line.description}
                          </div>
                          <div className="secondary-cell">
                            Confidence
                            {" "}
                            {Math.round(
                              Number(
                                line.confidence,
                              ) * 100,
                            )}
                            %
                          </div>
                        </td>
                        <td>
                          {line.quantity ?? "—"}
                        </td>
                        <td>
                          {formatMoney(
                            line.unit_price,
                            line.currency,
                          )}
                        </td>
                        <td className="amount-cell">
                          {formatMoney(
                            line.line_total,
                            line.currency,
                          )}
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </article>

        <aside className="detail-sidebar">
          <article className="panel">
            <div className="panel-header">
              <div>
                <div className="panel-kicker">
                  Decision
                </div>
                <h2>Control outcome</h2>
              </div>
            </div>

            <div className="control-stack">
              <div className="control-row">
                <span>Validation</span>
                <StatusBadge
                  value={
                    document.validation_outcome
                  }
                />
              </div>
              <div className="control-row">
                <span>Duplicate check</span>
                <StatusBadge
                  value={
                    document.duplicate_outcome
                  }
                />
              </div>
              <div className="control-row">
                <span>Vendor match</span>
                <StatusBadge
                  value={
                    document.vendor_match_outcome
                  }
                />
              </div>
              <div className="control-row">
                <span>Purchase order</span>
                <StatusBadge
                  value={
                    document.po_match_outcome
                  }
                />
              </div>
            </div>

            {detail.decision?.explanation && (
              <p className="decision-copy">
                {detail.decision.explanation}
              </p>
            )}
          </article>

          {detail.review_case && (
            <article className="panel">
              <div className="panel-header">
                <div>
                  <div className="panel-kicker">
                    Human review
                  </div>
                  <h2>
                    Case
                    {" "}
                    {detail.review_case.version}
                  </h2>
                </div>
                <StatusBadge
                  value={
                    detail.review_case.status
                  }
                />
              </div>

              <p className="decision-copy">
                {detail.review_case.explanation}
              </p>

              <div className="mini-meta">
                <span>
                  Owner
                </span>
                <strong>
                  {detail.review_case
                    .claimed_by_email ??
                    "Unclaimed"}
                </strong>
              </div>
            </article>
          )}

          <article className="panel">
            <div className="panel-header">
              <div>
                <div className="panel-kicker">
                  Downstream
                </div>
                <h2>Exports & delivery</h2>
              </div>
            </div>

            <div className="summary-counts">
              <div>
                <strong>
                  {detail.exports.length}
                </strong>
                <span>Exports</span>
              </div>
              <div>
                <strong>
                  {detail.notifications.length}
                </strong>
                <span>Notifications</span>
              </div>
            </div>

            <div className="activity-list">
              {detail.exports
                .slice(0, 3)
                .map((item) => (
                  <div
                    key={item.id}
                    className="activity-row"
                  >
                    <div>
                      <strong>
                        {item.export_format}
                        {" "}
                        export
                      </strong>
                      <span>
                        {formatDateTime(
                          item.requested_at,
                        )}
                      </span>
                    </div>
                    <StatusBadge
                      value={item.status}
                    />
                  </div>
                ))}

              {detail.notifications
                .slice(0, 3)
                .map((item) => (
                  <div
                    key={item.id}
                    className="activity-row"
                  >
                    <div>
                      <strong>
                        {humanize(item.channel)}
                      </strong>
                      <span>
                        {item.attempt_count}
                        /
                        {item.max_attempts}
                        {" "}
                        attempts
                      </span>
                    </div>
                    <StatusBadge
                      value={item.status}
                    />
                  </div>
                ))}

              {detail.exports.length === 0 &&
                detail.notifications.length ===
                  0 && (
                  <p className="muted-copy">
                    No downstream activity yet.
                  </p>
                )}
            </div>
          </article>
        </aside>
      </section>
    </div>
  );
}
