import { formatDate } from './Text.jsx'
import { SLUG } from './Panel.jsx'

// The chapters as a strip where width is time. A list makes a two-month stretch and a
// six-year one look the same size; this does not, which is the whole point — "what
// changes next" is a question about how soon, and a list cannot answer it.
//
// Shared between the overview, where it shows the next few years in a small space, and
// the timeline page, where it is the page.

function strongest(chapter) {
  return [...chapter.domains].sort((a, b) => Math.abs(b.score) - Math.abs(a.score))[0]
}

export default function Band({ chapters, open, onPick, compact, everyYears = 2 }) {
  if (!chapters?.length) return null

  const first = new Date(chapters[0].start).getTime()
  const last = new Date(chapters[chapters.length - 1].end).getTime()
  const span = last - first || 1
  const position = (iso) => ((new Date(iso).getTime() - first) / span) * 100

  const years = []
  const from = new Date(chapters[0].start).getFullYear() + 1
  const to = new Date(chapters[chapters.length - 1].end).getFullYear()
  for (let year = from; year <= to; year += everyYears) years.push(year)

  return (
    <div className={`band${compact ? ' compact' : ''}`}>
      {years.map((year) => (
        <span key={year} className="year" style={{ left: `${position(`${year}-01-01`)}%` }}>
          {year}
        </span>
      ))}
      {chapters.map((chapter) => {
        const lead = strongest(chapter)
        const width = position(chapter.end) - position(chapter.start)
        // Labelling each block with its ruling planet gave ten blocks reading
        // "Jupiter" — jargon, repeated, and clipped on the narrow ones. What the
        // chapter speaks to is the useful label, and only if it will fit. The compact
        // strip carries no labels at all: sitting under a headline about family, a
        // block reading "Finance" looks like a contradiction rather than a later
        // chapter, and the strip's job there is the shape of the years, not the detail.
        const label = !compact && width > 7 ? lead.domain : ''
        return (
          <button
            key={chapter.start}
            type="button"
            className={[
              'chapter', SLUG(lead.verdict),
              chapter.current ? 'current' : '',
              open === chapter.start ? 'open' : '',
            ].filter(Boolean).join(' ')}
            style={{ left: `${position(chapter.start)}%`, width: `${width}%` }}
            title={`${formatDate(chapter.start)} – ${formatDate(chapter.end)}: ${chapter.headline}`}
            onClick={() => onPick && onPick(open === chapter.start ? null : chapter.start)}
          >
            <span>{label}</span>
          </button>
        )
      })}
    </div>
  )
}
