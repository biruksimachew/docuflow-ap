import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import {
  formatDateTime,
  formatMoney,
} from "@/lib/format";
import type {
  DashboardDocument,
} from "@/lib/types";


export function InvoiceTable({
  documents,
  compact = false,
}: {
  documents: DashboardDocument[];
  compact?: boolean;
}) {
  if (documents.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon">
          0
        </div>
        <h3>No invoices found</h3>
        <p>
          New invoices will appear here after
          intake and processing.
        </p>
      </div>
    );
  }

  return (
    <div className="table-shell">
      <table className="data-table">
        <thead>
          <tr>
            <th>Invoice</th>
            <th>Vendor</th>
            <th>Status</th>
            {!compact && <th>PO match</th>}
            <th>Amount</th>
            <th>Received</th>
            <th aria-label="Open" />
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.id}>
              <td>
                <div className="primary-cell">
                  {document.invoice_number ??
                    "Pending extraction"}
                </div>
                <div className="secondary-cell">
                  {document.original_filename}
                </div>
              </td>
              <td>
                <div className="primary-cell">
                  {document.vendor_name ??
                    "Unresolved vendor"}
                </div>
              </td>
              <td>
                <StatusBadge
                  value={document.status}
                />
              </td>
              {!compact && (
                <td>
                  <StatusBadge
                    value={
                      document.po_match_outcome
                    }
                  />
                </td>
              )}
              <td className="amount-cell">
                {formatMoney(
                  document.total_amount,
                  document.currency,
                )}
              </td>
              <td className="muted-cell">
                {formatDateTime(
                  document.created_at,
                )}
              </td>
              <td>
                <Link
                  className="table-link"
                  href={`/documents/${document.id}`}
                  aria-label={`Open ${document.original_filename}`}
                >
                  →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
