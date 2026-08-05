import { InvoiceTable } from "@/components/invoice-table";
import { Pagination } from "@/components/pagination";
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

const sortOptions = [
  {
    value: "created_at",
    label: "Created date",
  },
  {
    value: "updated_at",
    label: "Last updated",
  },
  {
    value: "vendor_name",
    label: "Vendor",
  },
  {
    value: "invoice_number",
    label: "Invoice number",
  },
  {
    value: "total_amount",
    label: "Total amount",
  },
];

const PAGE_SIZE = 20;


type InvoicePageProps = {
  searchParams: Promise<{
    status?: string;
    search?: string;
    sort?: string;
    direction?: string;
    page?: string;
  }>;
};


function positivePage(
  value: string | undefined,
): number {
  const parsed = Number.parseInt(
    value ?? "1",
    10,
  );

  return Number.isFinite(parsed) &&
    parsed > 0
    ? parsed
    : 1;
}


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

  const sort = sortOptions.some(
    (option) =>
      option.value === params.sort,
  )
    ? params.sort!
    : "created_at";

  const direction =
    params.direction === "asc"
      ? "asc"
      : "desc";

  const page = positivePage(
    params.page,
  );

  const offset =
    (page - 1) * PAGE_SIZE;

  const query = new URLSearchParams();

  if (status) {
    query.set(
      "status",
      status,
    );
  }

  if (search) {
    query.set(
      "search",
      search,
    );
  }

  query.set(
    "sort_by",
    sort,
  );

  query.set(
    "sort_direction",
    direction,
  );

  query.set(
    "limit",
    String(PAGE_SIZE),
  );

  query.set(
    "offset",
    String(offset),
  );

  const result =
    await docuFlowFetch<DocumentListResponse>(
      `/api/v1/dashboard/documents?${query.toString()}`,
    );

  const totalPages = Math.max(
    1,
    Math.ceil(
      result.pagination.total /
      PAGE_SIZE,
    ),
  );

  const safePage = Math.min(
    page,
    totalPages,
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
            Search, sort and inspect every
            invoice from intake through
            downstream delivery.
          </p>
        </div>

        <div className="result-count">
          {result.pagination.total}
          <span>invoices</span>
        </div>
      </section>

      <section className="panel">
        <form
          className="filter-bar filter-bar-expanded"
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
            <span className="filter-label">
              Status
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

          <label className="select-field">
            <span className="filter-label">
              Sort by
            </span>
            <select
              name="sort"
              defaultValue={sort}
            >
              {sortOptions.map(
                (option) => (
                  <option
                    key={option.value}
                    value={option.value}
                  >
                    {option.label}
                  </option>
                ),
              )}
            </select>
          </label>

          <label className="select-field">
            <span className="filter-label">
              Direction
            </span>
            <select
              name="direction"
              defaultValue={direction}
            >
              <option value="desc">
                Descending
              </option>
              <option value="asc">
                Ascending
              </option>
            </select>
          </label>

          <button
            className="filter-button"
            type="submit"
          >
            Apply
          </button>
        </form>

        <InvoiceTable
          documents={result.documents}
        />

        <Pagination
          basePath="/invoices"
          currentPage={safePage}
          pageSize={PAGE_SIZE}
          total={result.pagination.total}
          params={{
            status,
            search,
            sort,
            direction,
          }}
        />
      </section>
    </div>
  );
}
