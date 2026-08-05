import Link from "next/link";

import { Pagination } from "@/components/pagination";
import { StatusBadge } from "@/components/status-badge";
import {
  docuFlowFetch,
  requireProfile,
} from "@/lib/api";
import {
  formatDateTime,
  formatMoney,
} from "@/lib/format";
import type {
  ReviewListResponse,
} from "@/lib/types";


const statuses = [
  "",
  "OPEN",
  "CLAIMED",
  "RESOLVED_APPROVED",
  "RESOLVED_REJECTED",
  "CANCELLED",
];

const owners = [
  {
    value: "ALL",
    label: "All ownership",
  },
  {
    value: "UNCLAIMED",
    label: "Unclaimed",
  },
  {
    value: "MINE",
    label: "Assigned to me",
  },
  {
    value: "CLAIMED",
    label: "Any claimed case",
  },
];

const sortOptions = [
  {
    value: "priority",
    label: "Priority",
  },
  {
    value: "created_at",
    label: "Created date",
  },
  {
    value: "updated_at",
    label: "Last updated",
  },
  {
    value: "total_amount",
    label: "Total amount",
  },
];

const PAGE_SIZE = 12;


type ReviewsPageProps = {
  searchParams: Promise<{
    status?: string;
    search?: string;
    owner?: string;
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
  title: "Review queue",
};


export default async function ReviewsPage({
  searchParams,
}: ReviewsPageProps) {
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
            status, propose corrections from
            an invoice workspace, and generate
            exports. Review queue ownership
            remains limited to reviewers and
            administrators.
          </p>
        </section>
      </div>
    );
  }

  const params = await searchParams;

  const status =
    params.status?.trim().toUpperCase() ?? "";

  const search =
    params.search?.trim() ?? "";

  const owner = owners.some(
    (option) =>
      option.value === params.owner,
  )
    ? params.owner!
    : "ALL";

  const sort = sortOptions.some(
    (option) =>
      option.value === params.sort,
  )
    ? params.sort!
    : "priority";

  const direction =
    params.direction === "desc"
      ? "desc"
      : "asc";

  const page = positivePage(
    params.page,
  );

  const offset =
    (page - 1) * PAGE_SIZE;

  const query =
    new URLSearchParams();

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
    "owner",
    owner,
  );

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
    await docuFlowFetch<ReviewListResponse>(
      `/api/v1/dashboard/reviews?${query.toString()}`,
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
            Human review
          </div>
          <h1>Exception queue</h1>
          <p>
            Filter by status and ownership,
            then open a case to correct,
            rerun and resolve it.
          </p>
        </div>

        <div className="result-count">
          {result.pagination.total}
          <span>cases</span>
        </div>
      </section>

      <section className="panel">
        <form
          className="filter-bar filter-bar-expanded review-filter-bar"
          action="/reviews"
          method="get"
        >
          <label className="search-field">
            <span className="sr-only">
              Search review cases
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
              Ownership
            </span>
            <select
              name="owner"
              defaultValue={owner}
            >
              {owners.map((option) => (
                <option
                  key={option.value}
                  value={option.value}
                >
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="select-field">
            <span className="filter-label">
              Sort
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
              <option value="asc">
                Ascending
              </option>
              <option value="desc">
                Descending
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

        <section className="review-grid review-grid-inside-panel">
          {result.reviews.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">
                ✓
              </div>
              <h3>No matching review cases</h3>
              <p>
                Change the filters or wait for
                another invoice exception.
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

                <div className="review-owner">
                  <span>Owner</span>
                  <strong>
                    {review.claimed_by_email ??
                      "Unclaimed"}
                  </strong>
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

        <Pagination
          basePath="/reviews"
          currentPage={safePage}
          pageSize={PAGE_SIZE}
          total={result.pagination.total}
          params={{
            status,
            search,
            owner,
            sort,
            direction,
          }}
        />
      </section>
    </div>
  );
}
