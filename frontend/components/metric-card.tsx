type MetricCardProps = {
  eyebrow: string;
  value: string | number;
  detail: string;
  tone?: "default" | "accent" | "warning";
};


export function MetricCard({
  eyebrow,
  value,
  detail,
  tone = "default",
}: MetricCardProps) {
  return (
    <article
      className={`metric-card metric-${tone}`}
    >
      <div className="metric-eyebrow">
        {eyebrow}
      </div>
      <div className="metric-value">
        {value}
      </div>
      <p className="metric-detail">
        {detail}
      </p>
    </article>
  );
}
