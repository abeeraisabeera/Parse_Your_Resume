export function StatCard({ label, value, helper, tone = "default", icon: Icon }) {
  return (
    <article className={`dg-kpi statCard ${tone}`}>
      {Icon ? (
        <span className="dg-kpi-icon" aria-hidden="true">
          <Icon size={20} />
        </span>
      ) : null}
      <span className="dg-kpi-label">{label}</span>
      <strong className="dg-kpi-value">{value}</strong>
      {helper ? <small className="dg-kpi-helper">{helper}</small> : null}
    </article>
  );
}
