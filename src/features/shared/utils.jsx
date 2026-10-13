export function formatReportTime(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value));
}

const DEFAULT_VALIDITY_DAYS = 14;

// The backend is the source of truth for how long a conclusion stays valid:
// every card carries validity_days and an expires_at filled by its validator.
// Offline demo cards have neither, so they fall back to the default rather than
// inventing a number that disagrees with the policy that produced the card.
export function remainingValidityDays(cards, fallback = DEFAULT_VALIDITY_DAYS) {
  const runtimeCard = cards?.find((card) => card?.runtimeCard?.expires_at)?.runtimeCard;
  if (!runtimeCard) {
    return cards?.find((card) => card?.runtimeCard?.validity_days)?.runtimeCard.validity_days ?? fallback;
  }
  const remainingMs = new Date(runtimeCard.expires_at).getTime() - Date.now();
  if (!Number.isFinite(remainingMs)) return fallback;
  return Math.max(0, Math.ceil(remainingMs / 86400000));
}

export function ScoreRing({ value, size = 42 }) {
  return (
    <div className="score-ring" style={{ '--score': `${value * 3.6}deg`, width: size, height: size }}>
      <span>{value}</span>
    </div>
  );
}
