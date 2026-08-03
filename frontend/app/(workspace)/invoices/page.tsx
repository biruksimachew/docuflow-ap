import { InvoiceTable } from "@/components/invoice-table";
import { docuFlowFetch } from "@/lib/api";
import type {
  DocumentListResponse,
} from "@/lib/types";


const statuses = [
  "",
  "AUTO_APPROVED",
  "REVIEW_REQUIRED",
  "REJECTED",
  "FAILED",
];


type InvoicePageProps = {
  searchParams: Promise<{
    status?: string;
    search?: string;
  }>;
};


export const metadata = {
  title: "Invoice queue",
};


export default async function InvoicesPage({
  searchParams,
}: InvoicePageProps) {
  const params = await searchParams;

  const status =
    params.status?.trim().toUpperCase() ?? "";
  const search =
    params.search?.trim() ?? "";

  const query = new URLSearchParams();

  if (status) {
    query.set("status", status);
  }

  if (search) {
    query.set("search", search);
  }

  query.set("limit", "100");

  const result =
    await docuFlowFetch<DocumentListResponse>(
      `/api/v1/dashboard/documents?${query.toString()}`,
    );

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <div className="eyebrow">
            Invoice operations
          </div>
          <h1>Invoice queue</h1>
          <p>
            Search invoices and inspect each
            document’s current control outcome.
          </p>
        </div>

        <div className="result-count">
          {result.pagination.total}
          <span>invoices</span>
        </div>
      </section>

      <section className="panel">
        <form
          className="filter-bar"
          action="/invoices"
          method="get"
        >
          <label className="search-field">
            <span className="sr-only">
              Search invoices
            </span>
            <svg
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle
                cx="11"
                cy="11"
                r="7"
              />
              <path d="m16 16 5 5" />
            </svg>
            <input
              type="search"
              name="search"
              defaultValue={search}
              placeholder="Search vendor, invoice or file…"
            />
          </label>

          <label className="select-field">
            <span className="sr-only">
              Filter status
            </span>
            <select
              name="status"
              defaultValue={status}
            >
              {statuses.map((value) => (
                <option
                  key={value || "ALL"}
                  value={value}
                >
                  {value
                    ? value.replaceAll(
                        "_",
                        " ",
                      )
                    : "ALL STATUSES"}
                </option>
              ))}
            </select>
          </label>

          <button
            className="filter-button"
            type="submit"
          >
            Apply filters
          </button>
        </form>

        <InvoiceTable
          documents={result.documents}
        />
      </section>
    </div>
  );
}
