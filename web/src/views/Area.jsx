import { Citation, Formatted, formatDate } from '../components/Text.jsx'
import { Meter, Panel, SLUG, Stat, Verdict, signTone, tone } from '../components/Panel.jsx'
import { section } from '../data.js'

// One life area, in two columns: the reading on the left, the numbers on the right.
//
// Before this everything sat in one stack, so the verdict, the score, the date it turns
// and the questions worth asking were four paragraphs to read in order rather than four
// things to glance at. The rail is the answer to "how is this, and when does it move";
// the column is the answer to "why".
export default function Area({ area, chart, stages, reading, onAsk }) {
  if (!chart || !stages) return <p className="plain">Loading…</p>

  const lower = area.toLowerCase()
  const written = section(reading, lower)
  const definition = stages.domains[area]
  const chapters = stages.stages
    .map((stage) => ({
      ...stage,
      reading: stage.domains.find((domain) => domain.domain === area),
    }))
    .filter((stage) => stage.reading)
  const current = chapters.find((stage) => stage.current)
  const index = chapters.indexOf(current)
  // The next chapter whose verdict differs is the one worth naming; the next chapter
  // full stop is often the same weather under a different sub-period.
  const turn = chapters
    .slice(index + 1)
    .find((stage) => stage.reading.verdict !== current?.reading.verdict)
  const relevant = (chart.yogas || []).filter((yoga) => yoga.domains.includes(area))

  const questions = [
    `What does my chart say about ${lower}?`,
    current ? `Why is ${lower} ${current.reading.verdict} right now?` : null,
    `When does ${lower} next change?`,
  ].filter(Boolean)

  return (
    <div className="area-view">
      <div className="page-head">
        <div>
          <h2>{area}</h2>
          <p className="sub">Read from {definition.why}</p>
        </div>
        {current && <Verdict verdict={current.reading.verdict} score={current.reading.score} />}
      </div>

      <div className="area-grid-2">
        <div className="area-main">
          <Panel tier={1} title="In short">
            {written ? (
              <div className="lead"><Formatted text={written.body} /></div>
            ) : (
              <>
                <p className="headline">
                  {current
                    ? `${current.reading.drivers[0]?.text || 'Nothing stands out either way'}.`
                    : 'No chapter covers the present moment.'}
                </p>
                <p className="footnote">
                  Written from the computed detail. The longer reading for this area has
                  not been generated yet.
                </p>
              </>
            )}
          </Panel>

          {current && (
            <Panel title="What is behind that" meta={definition.citation}>
              <ul className="drivers">
                {current.reading.drivers.map((driver) => (
                  <li key={driver.text}>
                    {/* Reasons carry weights of one to three, so they are scaled
                        against three, not against the domain score's five. */}
                    <Meter score={driver.weight} max={3} colour={signTone} />
                    <span className="what">{driver.text}</span>
                    <span className={`weight ${signTone(driver.weight)}`}>
                      {driver.weight > 0 ? `+${driver.weight}` : driver.weight}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <Panel title="When this changes" meta={`${chapters.length} chapters ahead`}>
            <ol className="chapter-strip">
              {chapters.map((stage) => (
                <li
                  key={stage.start}
                  className={`${SLUG(stage.reading.verdict)}${stage.current ? ' current' : ''}`}
                >
                  <span className="when">{formatDate(stage.start)}</span>
                  <Meter score={stage.reading.score} />
                  <span className="what">
                    <Verdict verdict={stage.reading.verdict} score={stage.reading.score} />
                    {stage.reading.distinguishing && (
                      <span className="footnote">{stage.reading.distinguishing}</span>
                    )}
                  </span>
                </li>
              ))}
            </ol>
          </Panel>

          {relevant.length > 0 && (
            <Panel title="Combinations bearing on this" meta={`${relevant.length} found`}>
              <ul className="yoga-list">
                {relevant.map((yoga) => (
                  <li key={yoga.id} className={yoga.polarity}>
                    <p className="plain"><strong>{yoga.name}.</strong> {yoga.plain}</p>
                    <Citation
                      text={yoga.citation}
                      refer={yoga.citation_ref}
                      located={yoga.citation_located}
                    />
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>

        <aside className="area-rail">
          {current && (
            <Panel title="At a glance">
              <div className="stat-stack">
                <Stat
                  label="Right now"
                  value={current.reading.verdict}
                  note={`${current.reading.score > 0 ? '+' : ''}${current.reading.score} of a possible ±5`}
                  tone={tone(current.reading.score)}
                />
                <Stat
                  label="Holds until"
                  value={formatDate(current.end)}
                  note={turn
                    ? `then ${turn.reading.verdict}`
                    : 'no change in the years computed'}
                />
                <Stat
                  label="Reasons counted"
                  value={current.reading.drivers.length}
                  note={
                    `${current.reading.drivers.filter((d) => d.weight > 0).length} helping, `
                    + `${current.reading.drivers.filter((d) => d.weight < 0).length} costing`
                  }
                />
              </div>
            </Panel>
          )}

          <Panel title="Worth asking" tier={3}>
            <div className="prompts">
              {questions.map((question) => (
                <button key={question} type="button" onClick={() => onAsk(question)}>
                  {question}
                </button>
              ))}
            </div>
          </Panel>
        </aside>
      </div>
    </div>
  )
}
