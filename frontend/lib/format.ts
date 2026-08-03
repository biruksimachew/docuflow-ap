export function formatMoney(
  amount: string | null | undefined,
  currency: string | null | undefined,
): string {
  if (!amount) {
    return "—";
  }

  const numeric = Number(amount);

  if (!Number.isFinite(numeric)) {
    return `${currency ?? ""} ${amount}`.trim();
  }

  return new Intl.NumberFormat(
    "en-US",
    {
      style: "currency",
      currency: currency ?? "USD",
      maximumFractionDigits: 2,
    },
  ).format(numeric);
}


export function formatDateTime(
  value: string | null | undefined,
): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "en-US",
    {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    },
  ).format(date);
}


export function formatDate(
  value: string | null | undefined,
): string {
  if (!value) {
    return "—";
  }

  const date = new Date(
    `${value}T00:00:00`,
  );

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "en-US",
    {
      month: "short",
      day: "numeric",
      year: "numeric",
    },
  ).format(date);
}


export function humanize(
  value: string | null | undefined,
): string {
  if (!value) {
    return "Not available";
  }

  return value
    .toLowerCase()
    .split("_")
    .map(
      (segment) =>
        segment.charAt(0).toUpperCase() +
        segment.slice(1),
    )
    .join(" ");
}
