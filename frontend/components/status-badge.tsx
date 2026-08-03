import { humanize } from "@/lib/format";


const positiveStatuses = new Set([
  "AUTO_APPROVED",
  "PASSED_CONTROLS",
  "CLEAR",
  "MATCHED",
  "READY",
  "SUCCEEDED",
  "RESOLVED_APPROVED",
]);

const warningStatuses = new Set([
  "REVIEW_REQUIRED",
  "OPEN",
  "CLAIMED",
  "PENDING",
  "DELIVERING",
  "RETRY_SCHEDULED",
  "NOT_PROVIDED",
  "AMBIGUOUS",
]);

const dangerStatuses = new Set([
  "REJECTED",
  "FAILED",
  "BUSINESS_DUPLICATE",
  "POTENTIAL_DUPLICATE",
  "MISMATCHED",
  "NOT_FOUND",
  "UNMATCHED",
  "RESOLVED_REJECTED",
]);


export function StatusBadge({
  value,
}: {
  value: string | null | undefined;
}) {
  const normalized = value ?? "UNKNOWN";

  let tone = "neutral";

  if (positiveStatuses.has(normalized)) {
    tone = "positive";
  } else if (
    warningStatuses.has(normalized)
  ) {
    tone = "warning";
  } else if (
    dangerStatuses.has(normalized)
  ) {
    tone = "danger";
  }

  return (
    <span
      className={`status-badge status-${tone}`}
    >
      <span
        className="status-dot"
        aria-hidden="true"
      />
      {humanize(normalized)}
    </span>
  );
}
