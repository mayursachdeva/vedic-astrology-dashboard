import { useGlossary } from '../glossary.js'
import { Citation, Term } from './Text.jsx'

function Yogas({ chart }) {
  const yogas = chart.yogas || []
  if (!yogas.length) {
    return (
      <section className="yogas">
        <h3>Combinations</h3>
        <p className="plain">
          None of the classical combinations currently encoded are present in this
          chart. That is a statement about the rules checked so far, not a verdict on
          the chart.
        </p>
      </section>
    )
  }

  const helpful = yogas.filter((yoga) => yoga.polarity === 'benefic')
  const difficult = yogas.filter((yoga) => yoga.polarity === 'malefic')

  const render = (list, heading) =>
    list.length > 0 && (
      <>
        <h4>{heading}</h4>
        <ul className="yoga-list">
          {list.map((yoga) => (
            <li key={yoga.id} className={yoga.polarity}>
              <p className="plain">
                <strong>{yoga.name}.</strong> {yoga.plain}
              </p>
              <div className="domains">
                {yoga.domains.map((domain) => (
                  <span key={domain} className="chip">{domain}</span>
                ))}
              </div>
              <details className="technical">
                <summary>Why this fired</summary>
                <p>{yoga.summary}</p>
                <ul>
                  {yoga.evidence.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
                <Citation
                  text={yoga.citation}
                  refer={yoga.citation_ref}
                  located={yoga.citation_located}
                />
                {yoga.note && <p className="citation">Note: {yoga.note}</p>}
              </details>
            </li>
          ))}
        </ul>
      </>
    )

  return (
    <section className="yogas">
      <h3>Combinations</h3>
      <p className="plain">
        Classical combinations present in this chart. Each one is a rule from a named
        text, and every claim below can be traced to the placements that triggered it.
      </p>
      {render(helpful, 'Supportive')}
      {render(difficult, 'Challenging')}
    </section>
  )
}


function Remedies({ remedies }) {
  if (!remedies) return null
  if (remedies.nothing_indicated) {
    return (
      <section className="remedies">
        <h3>Remedies</h3>
        <p className="plain">Nothing indicated by the rules currently encoded.</p>
      </section>
    )
  }
  return (
    <section className="remedies">
      <h3>Remedies</h3>
      <p className="footnote">{remedies.disclaimer}</p>
      {Object.entries(remedies.by_source).map(([source, list]) => (
        <div key={source}>
          <h4>From {source}</h4>
          <ul className="yoga-list">
            {list.map((r) => (
              <li key={r.id}>
                <p className="plain"><strong>{r.name}.</strong> {r.plain}</p>
                <details className="technical">
                  <summary>Why this applies</summary>
                  <p>{r.summary}</p>
                  <Citation
                    text={r.citation}
                    refer={r.citation_ref}
                    located={r.citation_located}
                  />
                  {r.note && <p className="citation">Note: {r.note}</p>}
                </details>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  )
}


function Ashtakavarga({ chart }) {
  const data = chart.ashtakavarga
  if (!data) return null
  const most = Math.max(...data.houses.map((house) => house.sav))

  return (
    <section className="ashtakavarga">
      <h3>House support</h3>
      <p className="plain">
        A points system that scores each house out of the whole chart. Houses with{' '}
        {data.thresholds.strong} points or more tend to deliver their matters more
        easily; {data.thresholds.weak} or fewer take more effort. The twelve always add
        up to {data.sav_total}.
      </p>
      <ol className="sav">
        {data.houses.map((house) => (
          <li key={house.house} className={house.reading}>
            <span className="label">
              {house.house}
              <small>{house.sign_name}</small>
            </span>
            <span className="bar" style={{ width: `${(house.sav / most) * 100}%` }} />
            <span className="count">{house.sav}</span>
          </li>
        ))}
      </ol>
      <details className="technical">
        <summary>Per-planet totals (Bhinnashtakavarga)</summary>
        <dl>
          {Object.entries(data.totals).map(([body, total]) => (
            <div key={body}>
              <dt>{body}</dt>
              <dd>{total}</dd>
            </div>
          ))}
        </dl>
      </details>
    </section>
  )
}

// Named for the reader rather than for the tradition; the Sanskrit is in the table
// header, where someone checking the arithmetic will look for it.
const SOURCE_NAMES = {
  sthana: 'where it sits',
  dig: 'its direction',
  kala: 'the hour it was born under',
  chesta: 'its motion',
  naisargika: 'its own nature',
  drik: 'what other planets throw at it',
}

function Shadbala({ chart }) {
  const data = chart.shadbala
  if (!data) return null
  const entries = Object.entries(data.grahas).sort((a, b) => b[1].ratio - a[1].ratio)
  const most = Math.max(...entries.map(([, bala]) => bala.ratio))

  return (
    <section className="shadbala">
      <h3>Planet strength</h3>
      <p className="plain">
        Six measures added together, deciding how much each planet can actually deliver
        — a well-placed planet that is weak here tends to promise more than it gives.
        Each planet has its own pass mark, and the bars below show how far past its own
        mark each one is. By raw total it is <strong>{data.strongest}</strong> that is
        strongest here, which the texts say is the planet a house's promise tends to
        come through.
        {!data.hour_based_parts && (
          <> Two of the six need a sunrise, and this birthplace has none at that
            time of year, so those are left out rather than guessed.</>
        )}
      </p>
      <ol className="sav">
        {entries.map(([body, bala]) => (
          <li key={body} className={bala.strong ? 'strong' : 'weak'}>
            <span className="label">
              {body}
              <small>{bala.rupas} rupas</small>
            </span>
            <span className="bar" style={{ width: `${(bala.ratio / most) * 100}%` }} />
            <span className="count">{Math.round(bala.ratio * 100)}%</span>
          </li>
        ))}
      </ol>
      <details className="technical">
        <summary>Where each planet's strength comes from (virupas)</summary>
        <table className="positions">
          <thead>
            <tr>
              <th>Graha</th>
              {Object.keys(SOURCE_NAMES).map((key) => (
                <th key={key} title={SOURCE_NAMES[key]}>{key}</th>
              ))}
              <th>total</th>
              <th>needs</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([body, bala]) => (
              <tr key={body}>
                <td>{body}</td>
                {Object.keys(SOURCE_NAMES).map((key) => (
                  <td key={key}>{bala.sources[key]}</td>
                ))}
                <td>{bala.total}</td>
                <td>{bala.required}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}

function Karakas({ chart }) {
  const data = chart.karakas
  if (!data) return null
  return (
    <section className="karakas">
      <h3>What each planet stands for in this chart</h3>
      <p className="plain">
        Read by degree alone: rank the planets by how far each has travelled into
        whatever sign it holds, and the order assigns the roles. Nothing about where
        they sit counts. <strong>{data.atma_karaka}</strong> has gone furthest, which
        the texts make the planet the whole chart runs through.
      </p>
      <table className="positions">
        <caption>Chara karakas, Brihat Parashara Hora Shastra ch. 32</caption>
        <thead>
          <tr><th>Role</th><th>Stands for</th><th>Planet</th><th>Degrees in</th></tr>
        </thead>
        <tbody>
          {data.karakas.map((entry) => (
            <tr key={entry.role}>
              <td>{entry.role}</td>
              <td>{entry.means}</td>
              <td>
                {entry.body}
                {entry.counted_backwards && (
                  <small title="Rahu moves backwards, so its degree is counted from 30">
                    {' '}counted back
                  </small>
                )}
              </td>
              <td>{entry.degree.toFixed(2)}°</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function PositionsTable({ chart }) {
  const retrograde = useGlossary().terms.retrograde?.definition || ''

  return (
    <table className="positions">
      {/* The panel around this already says "Positions", so the caption earns its
          place by saying which zodiac these are measured in rather than repeating. */}
      <caption>Sidereal longitudes, whole-sign houses</caption>
      <thead>
        <tr>
          <th>Planet</th><th>Sign</th><th>Degree</th><th>House</th>
          <th><Term name="Nakshatra">Nakshatra</Term></th>
          <th><Term name="Pada">Pada</Term></th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(chart.positions).map(([body, position]) => (
          <tr key={body}>
            <td>
              {body}
              {position.retrograde && (
                <span className="retro" title={retrograde}> R</span>
              )}
            </td>
            <td>{position.sign_name}</td>
            <td>{position.degree_in_sign.toFixed(2)}°</td>
            <td>{position.house}</td>
            <td>{position.nakshatra_name}</td>
            <td>{position.pada}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export { Yogas, Remedies, Ashtakavarga, Shadbala, Karakas, PositionsTable }
