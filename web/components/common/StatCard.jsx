export function StatCard({ label, value, helper, tone = "default" }) {
  return (
    <article className={`metricCard statCard ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {helper ? <small>{helper}</small> : null}
    </article>
  );
}
