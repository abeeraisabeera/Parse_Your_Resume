import { statusClassName } from "../../lib/candidateUtils";

export function StatusBadge({ status }) {
  return (
    <mark className={`statusBadge ${statusClassName(status)}`}>
      {status || "New"}
    </mark>
  );
}
