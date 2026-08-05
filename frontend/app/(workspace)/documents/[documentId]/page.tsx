import Link from "next/link";

import {
  DocumentOperations,
} from "@/components/document-operations";
import {
  StatusBadge,
} from "@/components/status-badge";
import {
  docuFlowFetch,
  requireProfile,
} from "@/lib/api";
import {
  formatDate,
  formatMoney,
  humanize,
} from "@/lib/format";
import type {
  DocumentDetailResponse,
  EffectiveInvoiceSnapshot,
  ReviewSnapshot,
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
  const {
    documentId,
  } = await params;

  const [
    profile,
    detail,
  ] = await Promise.all([
    requireProfile(),
    docuFlowFetch<DocumentDetailResponse>(
      `/api/v1/dashboard/documents/${documentId}`,
    ),
  ]);

  let reviewSnapshot:
    ReviewSnapshot | null = null;

  let effectiveInvoice:
    EffectiveInvoiceSnapshot | null = null;

  if (detail.review_case) {
    [
      reviewSnapshot,
      effectiveInvoice,
    ] = await Promise.all([
      docuFlowFetch<ReviewSnapshot>(
        `/api/v1/reviews/${detail.review_case.id}`,
      ),
      docuFlowFetch<EffectiveInvoiceSnapshot>(
        `/api/v1/reviews/${detail.review_case.id}/effective-invoice`,
      ),
    ]);
  }

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
                {document.vendor_name ??
                  "—"}
              </dd>
            </div>
            <div>
              <dt>Invoice number</dt>
              <dd>
                {document.invoice_number ??
                  "—"}
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
            <div>
              <dt>Subtotal</dt>
              <dd>
                {formatMoney(
                  document.subtotal,
                  document.currency,
                )}
              </dd>
            </div>
            <div>
              <dt>Tax</dt>
              <dd>
                {formatMoney(
                  document.tax_amount,
                  document.currency,
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
                        <td>
                          {line.line_number}
                        </td>
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
                          {line.quantity ??
                            "—"}
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
                <span>Owner</span>
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
                <h2>Current evidence</h2>
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
                <span>Deliveries</span>
              </div>
            </div>
          </article>
        </aside>
      </section>

      <DocumentOperations
        user={{
          user_id:
            profile.user.user_id,
          email:
            profile.user.email,
          role:
            profile.user.role,
        }}
        documentId={documentId}
        documentStatus={
          document.status
        }
        lineItems={
          detail.line_items
        }
        reviewSnapshot={
          reviewSnapshot
        }
        effectiveInvoice={
          effectiveInvoice
        }
        exports={
          detail.exports
        }
        notifications={
          detail.notifications
        }
      />
    </div>
  );
}
