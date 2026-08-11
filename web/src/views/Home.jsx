import Kundli from '../Kundli.jsx'
import Band from '../components/Band.jsx'
import { Formatted, formatDate } from '../components/Text.jsx'
import { Meter, Panel, SLUG, Verdict } from '../components/Panel.jsx'
import { AREAS, section } from '../data.js'

// One screen, laid out rather than stacked. Three zones, each with a job:
//
//   the status band   what is true now, and how far through it you are
//   the focus row     the two or three areas this chapter actually moves
//   the rail          every area at a glance, the chart, and the way forward
//
// The previous version answered the same questions in one column of paragraphs, so
// nothing looked more important than anything else and the reader had to rank it.

function daysBetween(from, to) {
  return (new Date(to).getTime() - new Date(from).getTime()) / 86400000
}

export default function Home({
  chart, stages, reading, onOpenArea, onOpenTimeline, onOpenHouse,
}) {
  if (!chart) return <p className="plain">Loading…</p>

  const list = stages?.stages || []
  const current = list.find((stage) => stage.current)
  const next = list[list.indexOf(current) + 1]
  const overview = section(reading, 'overview')

  const ranked = current
    ? [...current.domains].sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
    : []
  const focus = ranked.filter((domain) => Math.abs(domain.score) >= 2).slice(0, 3)

  const months = current ? Math.round(daysBetween(current.start, current.end) / 30.4) : 0
  const runs = months >= 24
    ? `runs ${Math.round(months / 12)} years`
    : `runs ${months} month${months === 1 ? '' : 's'}`

  const bodies = Object.fromEntries(
    Object.entries(chart.positions).map(([body, position]) => [
      body,
      { house: position.house, sign: position.sign, retrograde: position.retrograde },
    ]),
  )

  return (
    <div className="home">
      <div className="page-head">
        <div>
          <h2>{chart.profile.name}</h2>
          <p className="sub">
            Born {formatDate(chart.birth.local)}
            {chart.profile.place ? ` in ${chart.profile.place}` : ''}
          </p>
        </div>
        {ranked[0] && (
          <span className="head-verdict">
            <small>loudest right now</small>
            <b>{ranked[0].domain}</b>
            <Verdict verdict={ranked[0].verdict} score={ranked[0].score} />
          </span>
        )}
      </div>

      {current && (
        <Panel
          tier={1}
          title="Where you are now"
          meta={`${runs}, to ${formatDate(current.end)}`}
        >
          <p className="headline">{current.headline}</p>
          {/* Width is time, so "what changes next" is answered by looking rather than
              by reading a date and working out how far away it is. */}
          <Band chapters={list.slice(0, 10)} compact onPick={onOpenTimeline} />
          {current.says && (
            <details className="source">
              <summary>
                What the texts say of {current.mahadasha}
                {current.antardasha ? `/${current.antardasha}` : ''} — {current.says.citation}
              </summary>
              <blockquote>{current.says.text}</blockquote>
            </details>
          )}
          <p className="footnote next-up">
            {next
              ? <>Next, from {formatDate(next.start)}:{' '}
                  {next.headline.charAt(0).toLowerCase() + next.headline.slice(1)}</>
              : 'No further chapter is computed.'}
          </p>
        </Panel>
      )}

      {/* Full width, above the split: these are the two or three things the chapter
          actually moves, and they were losing a card per row inside a column. */}
      {focus.length > 0 && (
        <Panel title="What this chapter moves" meta="tap one to open it">
          <ul className="area-cards">
            {focus.map((domain) => (
              <li key={domain.domain} className={SLUG(domain.verdict)}>
                <button type="button" onClick={() => onOpenArea(domain.domain)}>
                  <span className="card-top">
                    <strong>{domain.domain}</strong>
                    <Meter score={domain.score} />
                  </span>
                  <Verdict verdict={domain.verdict} score={domain.score} />
                  <span className="because">{domain.drivers[0]?.text}</span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="home-grid">
        <div className="home-main">
          {overview && (
            <Panel title="Your chart in short">
              <div className="lead"><Formatted text={overview.body} /></div>
            </Panel>
          )}

          <Panel title="Every area" meta="scored for this chapter">
            <ul className="area-rows">
              {AREAS.map((area) => {
                const domain = current?.domains.find((d) => d.domain === area)
                return (
                  <li key={area}>
                    <button type="button" onClick={() => onOpenArea(area)}>
                      <span className="name">{area}</span>
                      {domain
                        ? <Meter score={domain.score} label={`${area} ${domain.verdict}`} />
                        : <span />}
                      <span className="why">{domain?.drivers[0]?.text || '—'}</span>
                      <span className="go">→</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </Panel>
        </div>

        <aside className="home-rail">
          <Panel title="The birth chart" meta={`${chart.lagna.sign_name} rising`}>
            <Kundli
              title=""
              lagnaSign={chart.lagna.sign}
              bodies={bodies}
              onSelectHouse={onOpenHouse}
            />
            <p className="footnote">
              Tap any house to read what it means, where it stands and what the texts
              prescribe for it.
            </p>
          </Panel>

          <Panel title="Next" tier={3}>
            <button type="button" className="wayfinder" onClick={onOpenTimeline}>
              <span>The years ahead</span>
              <small>{list.length} chapters computed</small>
            </button>
          </Panel>
        </aside>
      </div>
    </div>
  )
}
