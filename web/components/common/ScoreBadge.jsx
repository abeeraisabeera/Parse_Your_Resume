import { formatPercent } from "../../lib/candidateUtils";
import { scoreTier } from "../../lib/scoreUtils";

export function ScoreBadge({ score }) {
  const tier = scoreTier(score);
  return (
    <mark className={`scoreBadge scoreBadge--${tier}`}>
      {formatPercent(score)}
    </mark>
  );
}
