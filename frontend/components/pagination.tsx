import Link from "next/link";


type PaginationProps = {
  basePath: string;
  currentPage: number;
  pageSize: number;
  total: number;
  params: Record<
    string,
    string | undefined
  >;
};


function pageHref(
  basePath: string,
  page: number,
  params: Record<
    string,
    string | undefined
  >,
): string {
  const query =
    new URLSearchParams();

  for (
    const [key, value]
    of Object.entries(params)
  ) {
    if (
      value &&
      key !== "page"
    ) {
      query.set(
        key,
        value,
      );
    }
  }

  query.set(
    "page",
    String(page),
  );

  return `${basePath}?${query.toString()}`;
}


export function Pagination({
  basePath,
  currentPage,
  pageSize,
  total,
  params,
}: PaginationProps) {
  const totalPages = Math.max(
    1,
    Math.ceil(total / pageSize),
  );

  const previousPage = Math.max(
    1,
    currentPage - 1,
  );

  const nextPage = Math.min(
    totalPages,
    currentPage + 1,
  );

  const start =
    total === 0
      ? 0
      : (
          (currentPage - 1) *
          pageSize
        ) + 1;

  const end = Math.min(
    total,
    currentPage * pageSize,
  );

  return (
    <nav
      className="pagination"
      aria-label="Pagination"
    >
      <div className="pagination-summary">
        Showing
        {" "}
        <strong>{start}</strong>
        {" "}
        to
        {" "}
        <strong>{end}</strong>
        {" "}
        of
        {" "}
        <strong>{total}</strong>
      </div>

      <div className="pagination-controls">
        {currentPage > 1 ? (
          <Link
            className="pagination-link"
            href={pageHref(
              basePath,
              previousPage,
              params,
            )}
          >
            ← Previous
          </Link>
        ) : (
          <span className="pagination-link pagination-link-disabled">
            ← Previous
          </span>
        )}

        <span className="pagination-page">
          Page
          {" "}
          <strong>{currentPage}</strong>
          {" "}
          of
          {" "}
          <strong>{totalPages}</strong>
        </span>

        {currentPage < totalPages ? (
          <Link
            className="pagination-link"
            href={pageHref(
              basePath,
              nextPage,
              params,
            )}
          >
            Next →
          </Link>
        ) : (
          <span className="pagination-link pagination-link-disabled">
            Next →
          </span>
        )}
      </div>
    </nav>
  );
}
