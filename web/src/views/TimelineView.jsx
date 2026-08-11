import { useState } from 'react'
import Band from '../components/Band.jsx'
import { Formatted, formatDate } from '../components/Text.jsx'
import { Meter, Panel, SLUG, Stat, Verdict } from '../components/Panel.jsx'
import { section } from '../data.js'

// The chapters as a band across the years rather than a list to scroll. Width is time,
// so a two-month stretch and a six-year one no longer look the same size. Picking one
// fills the panel below it instead of pushing the band off the screen.
export default function TimelineView({ stages, reading, onOpenArea }) {
  const [open, setOpen] = useState(null)
  if (!stages) return <p className="plain">Loading…</p>

  const written = section(reading, 'timeline')
  const chapters = stages.stages
  const chosen = chapters.find((chapter) => chapter.start === open)
    || chapters.find((chapter) => chapter.current)

  const ranked = chosen
    ? [...chosen.domains].sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
    : []
  const good = ranked.filter((domain) => domain.score >= 2)
  const bad = ranked.filter((domain) => domain.score <= -2)

  return (
    <div className="timeline-view">
      <div className="page-head">
        <div>
          <h2>The years ahead</h2>
          <p className="sub">
            {chapters.length} chapters, from {formatDate(chapters[0].start)} to{' '}
            {formatDate(chapters[chapters.length - 1].end)}. Width is time.
          </p>
        </div>
      </div>

      <Panel tier={1} title="Every chapter" meta="pick one">
        <Band chapters={chapters} open={open} onPick={setOpen} />
      </Panel>

      {written && (
        <Panel title="In short">
          <div className="lead"><Formatted text={written.body} /></div>
        </Panel>
      )}

      {chosen && (
        <div className="area-grid-2">
          <div className="area-main">
            <Panel
              title={chosen.current ? 'The chapter running now' : 'The chapter you picked'}
              meta={`${formatDate(chosen.start)} – ${formatDate(chosen.end)}`}
            >
              <p className="headline">{chosen.headline}</p>
              <p className="footnote">Opens with: {chosen.opened_by.join('; ')}.</p>
              {chosen.says && (
                <>
                  <h4>What the texts say of this pair of periods</h4>
                  <p className="quoted">{chosen.says.text}</p>
                  <p className="citation">Source: {chosen.says.citation}</p>
                </>
              )}
              <ul className="area-cards">
                {ranked.map((domain) => (
                  <li key={domain.domain} className={SLUG(domain.verdict)}>
                    <button type="button" onClick={() => onOpenArea(domain.domain)}>
                      <span className="card-top">
                        <strong>{domain.domain}</strong>
                        <Meter score={domain.score} />
                      </span>
                      <Verdict verdict={domain.verdict} score={domain.score} />
                      <span className="because">{domain.drivers[0]?.text || '—'}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>

          <aside className="area-rail">
            <Panel title="At a glance">
              <div className="stat-stack">
                <Stat label="Helped" value={good.length || '—'}
                      note={good.map((d) => d.domain).join(', ') || 'nothing strongly'}
                      tone={good.length ? 'good' : undefined} />
                <Stat label="Under strain" value={bad.length || '—'}
                      note={bad.map((d) => d.domain).join(', ') || 'nothing strongly'}
                      tone={bad.length ? 'bad' : undefined} />
                <Stat label="Ruled by" value={chosen.mahadasha}
                      note={chosen.antardasha ? `sub-period of ${chosen.antardasha}` : ''} />
              </div>
            </Panel>
          </aside>
        </div>
      )}
    </div>
  )
}
