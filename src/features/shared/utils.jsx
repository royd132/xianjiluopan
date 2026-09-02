export function formatReportTime(value) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value));
}

export function ScoreRing({ value, size = 42 }) {
  return (
    <div className="score-ring" style={{ '--score': `${value * 3.6}deg`, width: size, height: size }}>
      <span>{value}</span>
    </div>
  );
}
