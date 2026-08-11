// The pieces the dashboard is assembled from.
//
// Before this, everything on a page was a paragraph with a different font size, so the
// only way to tell what mattered was to read it all. These give each thing an edge, a
// place and a weight: a panel is a box you can point at, a meter shows a score without
// being read, and a verdict is a coloured word rather than a number to interpret.

const SLUG = (verdict) => (verdict || '').replace(/ /g, '-')

// Domain scores run roughly -6 to +6; five is where the bar fills.
const FULL = 5

/** The colour of a domain score, matching the verdict the server computes from it. */
export function tone(score) {
  if (score >= 2) return 'good'
  if (score <= -2) return 'bad'
  return 'flat'
}

/**
 * The colour of one reason.
 *
 * Not the same question as `tone`. A domain sitting at +1 is genuinely mixed — that is
 * what the verdict says — but a reason weighted +1 is unambiguously helping, and
 * colouring it neutral told the reader the opposite of the arithmetic.
 */
export function signTone(weight) {
  if (weight > 0) return 'good'
  if (weight < 0) return 'bad'
  return 'flat'
}

/** A box with a label, which is what gives a thing its own place on the page. */
export function Panel({ title, meta, tier = 2, wide, className = '', children }) {
  return (
    <section className={`panel tier-${tier}${wide ? ' wide' : ''} ${className}`.trim()}>
      {(title || meta) && (
        <header className="panel-head">
          {title && <h3>{title}</h3>}
          {meta && <span className="panel-meta">{meta}</span>}
        </header>
      )}
      {children}
    </section>
  )
}

/**
 * A score, shown rather than written.
 *
 * Diverging from the centre, so support runs right and strain runs left. A column of
 * "+2 / 0 / -3" has to be read one row at a time; a column of these has a shape.
 */
export function Meter({ score, label, max = FULL, colour = tone }) {
  const share = (Math.min(Math.abs(score), max) / max) * 50
  const side = score >= 0 ? { left: '50%' } : { right: '50%' }
  return (
    <span
      className="meter"
      role="img"
      aria-label={label || `score ${score > 0 ? `+${score}` : score}`}
    >
      <span className="meter-axis" />
      <span className={`meter-fill ${colour(score)}`} style={{ ...side, width: `${share}%` }} />
    </span>
  )
}

/** The verdict as a coloured chip, so it reads at a glance and always the same way. */
export function Verdict({ verdict, score }) {
  return (
    <span className={`verdict-chip ${SLUG(verdict)}`}>
      {verdict}
      {score !== undefined && (
        <b>{score > 0 ? `+${score}` : score}</b>
      )}
    </span>
  )
}

/** One labelled number, for the rails where several sit side by side. */
export function Stat({ label, value, note, tone: t }) {
  return (
    <div className={`stat${t ? ` ${t}` : ''}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {note && <span className="stat-note">{note}</span>}
    </div>
  )
}

export { SLUG }
