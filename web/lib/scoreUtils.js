export function scoreTier(score) {
  const value = Number(score || 0);
  if (value >= 75) return "high";
  if (value >= 50) return "medium";
  return "low";
}
