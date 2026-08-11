import { Term, formatDate } from './Text.jsx'

function Panchanga({ panchanga }) {
  if (!panchanga) return null
  const row = (label, moment) => (
    <tr key={label}>
      <td>{label}</td>
      <td>{moment.tithi.name} <small>({moment.paksha})</small></td>
      <td>{moment.vara.name}</td>
      <td>{moment.nakshatra.name}</td>
      <td>{moment.yoga.name}</td>
      <td>{moment.karana.name}</td>
    </tr>
  )
  const flags = [...panchanga.birth.flags]

  return (
    <section className="panchanga">
      <h3>The day itself</h3>
      <p className="plain">
        The five limbs of the day — the lunar day, the weekday, the Moon's mansion, and
        two subdivisions. These describe the day a person was born into, alongside the
        chart of where the planets stood.
      </p>
      <table className="positions">
        <thead>
          <tr>
            <th></th><th>Tithi</th><th>Weekday</th><th>Nakshatra</th>
            <th>Yoga</th><th>Karana</th>
          </tr>
        </thead>
        <tbody>
          {row('At birth', panchanga.birth)}
          {row('Today', panchanga.today)}
        </tbody>
      </table>
      {flags.length > 0 && (
        <ul className="warnings">
          {flags.map((flag) => <li key={flag}>{flag}</li>)}
        </ul>
      )}
    </section>
  )
}


function Transits({ transits }) {
  if (!transits) return null
  const { gochara, windows, confluence } = transits
  const disagree = Object.entries(gochara).filter(([, g]) => !g.doctrines_agree)

  return (
    <section className="transits">
      <h3>Where the planets are now</h3>
      <p className="plain">
        As of {formatDate(transits.as_of)}. A planet is read as well supported when the
        sign it is crossing scores well in that planet's own points table — the reading
        Parashara gives — and separately by the older table counted from your Moon.
      </p>

      <p className={`plain reading ${confluence.reading}`}>
        Your current period looks <strong>{confluence.reading}</strong> by transit:{' '}
        {confluence.components
          .map((c) => `${c.lord} ${c.supported ? 'well placed' : 'poorly placed'}`)
          .join(', ')}
        .
      </p>

      <table className="positions">
        <caption>Transit standing</caption>
        <thead>
          <tr>
            <th>Planet</th><th>Sign</th><th>From Moon</th>
            <th>Points</th><th>Reading</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(gochara).map(([body, g]) => (
            <tr key={body} className={g.supported ? 'good' : 'poor'}>
              <td>{body}{g.retrograde ? <span className="retro"> R</span> : null}</td>
              <td>{g.sign_name}</td>
              <td>{g.house_from_moon}</td>
              <td>{g.bindus || '—'}</td>
              <td>{g.supported ? 'supported' : 'not supported'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {disagree.length > 0 && (
        <p className="footnote">
          The two traditions disagree about {disagree.map(([b]) => b).join(', ')}. Neither
          is treated as the winner here.
        </p>
      )}

      <h4>What changes next</h4>
      {windows.length === 0 ? (
        <p className="plain">Nothing notable in the period shown.</p>
      ) : (
        <ol className="timeline-list">
          {windows.map((w) => (
            <li key={`${w.kind}-${w.label}-${w.start}`} className={w.kind}>
              <span className="span">
                {formatDate(w.start)} – {formatDate(w.end)}
              </span>
              <strong>{w.label}</strong>
              {w.detail && <small> {w.detail}</small>}
            </li>
          ))}
        </ol>
      )}

      <details className="technical">
        <summary>How this is judged</summary>
        <p>{confluence.basis}</p>
        <ul>
          {confluence.components.map((c) => (
            <li key={c.level}>
              {c.level}: {c.lord} in {c.sign} — {c.bindus} points, weight {c.weight},
              contribution {c.contribution}
            </li>
          ))}
        </ul>
      </details>
    </section>
  )
}

export { Panchanga, Transits }
