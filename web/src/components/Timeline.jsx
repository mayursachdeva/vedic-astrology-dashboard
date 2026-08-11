import { useState } from 'react'
import { Term, formatDate } from './Text.jsx'
import { reportUrl } from '../api.js'

function LifeStages({ stages, profileId }) {
  const [open, setOpen] = useState(null)
  if (!stages) return null

  return (
    <section className="stages">
      <h3>Your life in chapters</h3>
      <p className="plain">
        Each chapter runs from one change to the next — a new planetary period, or a slow
        planet moving into a new sign. The bars show which parts of life each chapter
        leans on. Open one to see exactly why.
      </p>
      <p className="plain">
        <a href={reportUrl(profileId)} target="_blank" rel="noreferrer">
          Read the full written report
        </a>
      </p>

      <ol className="stage-list">
        {stages.stages.map((stage) => {
          const strongest = [...stage.domains].sort(
            (a, b) => Math.abs(b.score) - Math.abs(a.score),
          )
          const isOpen = open === stage.start
          return (
            <li key={stage.start} className={stage.current ? 'current' : ''}>
              <button className="stage-head" onClick={() => setOpen(isOpen ? null : stage.start)}>
                <span className="when">
                  {formatDate(stage.start)} – {formatDate(stage.end)}
                  {stage.current && <span className="badge">now</span>}
                </span>
                <span className="what">{stage.headline}</span>
              </button>

              <ul className="domain-bars">
                {strongest.map((d) => (
                  <li key={d.domain} className={d.verdict.replace(/ /g, '-')}>
                    <span className="name">{d.domain}</span>
                    <span className="bar" style={{ width: `${Math.min(Math.abs(d.score), 5) * 18}px` }} />
                    <span className="score">{d.score > 0 ? `+${d.score}` : d.score}</span>
                  </li>
                ))}
              </ul>

              {isOpen && (
                <div className="stage-detail">
                  <p className="footnote">Opens with: {stage.opened_by.join('; ')}.</p>
                  {strongest.map((d) => (
                    <div key={d.domain}>
                      <strong>{d.domain}</strong> — {d.verdict}
                      <ul>
                        {d.drivers.map((driver) => (
                          <li key={driver.text}>
                            {driver.text} ({driver.weight > 0 ? '+' : ''}{driver.weight})
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}


function DashaTimeline({ chart, tree }) {
  const currentLords = chart.dasha.current.map((period) => period.lord)
  const today = Date.now()

  return (
    <section className="timeline">
      <h3>Life periods</h3>
      <p className="plain">
        Each block is a <Term name="Mahadasha">major period</Term> ruled by one planet.
        Expand one to see its <Term name="Antardasha">sub-periods</Term>.
      </p>
      <ol>
        {(tree || chart.dasha.mahadashas).map((period) => {
          const active =
            new Date(period.start).getTime() <= today &&
            today < new Date(period.end).getTime()
          return (
            <li key={period.start} className={active ? 'active' : ''}>
              <details open={active}>
                <summary>
                  <strong>{period.lord}</strong>
                  <span className="span">
                    {formatDate(period.start)} – {formatDate(period.end)}
                  </span>
                  <span className="years">{period.years.toFixed(1)} yr</span>
                  {active && <span className="badge">now</span>}
                </summary>
                {period.children && (
                  <ol className="sub">
                    {period.children.map((child) => {
                      const childActive =
                        new Date(child.start).getTime() <= today &&
                        today < new Date(child.end).getTime()
                      return (
                        <li key={child.start} className={childActive ? 'active' : ''}>
                          {period.lord} / <strong>{child.lord}</strong>
                          <span className="span">
                            {formatDate(child.start)} – {formatDate(child.end)}
                          </span>
                          {childActive && <span className="badge">now</span>}
                        </li>
                      )
                    })}
                  </ol>
                )}
              </details>
            </li>
          )
        })}
      </ol>
      <p className="footnote">
        Currently running: {currentLords.join(' / ') || 'outside the computed cycle'}.
      </p>
    </section>
  )
}

export default function App() {
  const [profiles, setProfiles] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [chart, setChart] = useState(null)
  const [tree, setTree] = useState(null)
  const [transits, setTransits] = useState(null)
  const [stages, setStages] = useState(null)
  const [remedies, setRemedies] = useState(null)
  const [panchanga, setPanchanga] = useState(null)
  const [varga, setVarga] = useState('D1')
  const [error, setError] = useState(null)

  useEffect(() => {
    listProfiles()
      .then((loaded) => {
        setProfiles(loaded)
        if (loaded.length && selectedId === null) setSelectedId(loaded[0].id)
      })
      .catch((problem) => setError(problem.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (selectedId === null) {
      setChart(null)
      setTree(null)
      setTransits(null)
      setStages(null)
      setRemedies(null)
      setPanchanga(null)
      return
    }
    setError(null)
    getChart(selectedId, '1,9,10')
      .then(setChart)
      .catch((problem) => setError(problem.message))
    getDashas(selectedId, 2).then(setTree).catch(() => setTree(null))
    getTransits(selectedId, 36).then(setTransits).catch(() => setTransits(null))
    getLifeStages(selectedId, 12).then(setStages).catch(() => setStages(null))
    getRemedies(selectedId).then(setRemedies).catch(() => setRemedies(null))
    getPanchanga(selectedId).then(setPanchanga).catch(() => setPanchanga(null))
  }, [selectedId])

  const bodies = useMemo(() => {
    if (!chart) return {}
    if (varga === 'D1') {
      return Object.fromEntries(
        Object.entries(chart.positions).map(([body, position]) => [
          body,
          { house: position.house, sign: position.sign, retrograde: position.retrograde },
        ]),
      )
    }
    const table = chart.vargas[varga]
    return Object.fromEntries(
      Object.entries(table.signs).map(([body, info]) => [
        body,
        { house: info.house, sign: info.sign, retrograde: chart.positions[body].retrograde },
      ]),
    )
  }, [chart, varga])

  const lagnaSign = chart
    ? varga === 'D1'
      ? chart.lagna.sign
      : chart.vargas[varga].lagna_sign
    : 0

  async function removeProfile(id) {
    await deleteProfile(id)
    const remaining = profiles.filter((profile) => profile.id !== id)
    setProfiles(remaining)
    if (selectedId === id) setSelectedId(remaining.length ? remaining[0].id : null)
  }

  return (
    <div className="layout">
      <aside>
        <h1>Charts</h1>
        <ul className="people">
          {profiles.map((profile) => (
            <li key={profile.id} className={profile.id === selectedId ? 'selected' : ''}>
              <button onClick={() => setSelectedId(profile.id)}>
                {profile.name}
                {profile.relation && <small> — {profile.relation}</small>}
              </button>
              <button className="remove" onClick={() => removeProfile(profile.id)} title="Remove">
                ×
              </button>
            </li>
          ))}
        </ul>
        <ProfileForm
          onCreated={(created) => {
            setProfiles([...profiles, created])
            setSelectedId(created.id)
          }}
        />
      </aside>

      <main>
        {error && <p className="error">{error}</p>}
        {!chart && !error && <p className="plain">Add a person to see their chart.</p>}
        {chart && (
          <>
            <Summary chart={chart} />
            <LifeStages stages={stages} profileId={selectedId} />
            <div className="charts">
              <nav className="tabs">
                {VARGAS.map((name) => (
                  <button
                    key={name}
                    className={name === varga ? 'active' : ''}
                    onClick={() => setVarga(name)}
                  >
                    {name === 'D1' ? 'Birth chart' : chart.vargas[name].name}
                  </button>
                ))}
              </nav>
              <Kundli
                title={
                  varga === 'D1'
                    ? `Rasi — ${chart.lagna.sign_name} rising`
                    : `${chart.vargas[varga].name} (${varga})`
                }
                lagnaSign={lagnaSign}
                bodies={bodies}
              />
              <PositionsTable chart={chart} />
            </div>
            <Yogas chart={chart} />
            <Ashtakavarga chart={chart} />
            <Ask profileId={selectedId} profileName={chart.profile.name} />
            <Library />
            <Panchanga panchanga={panchanga} />
            <Transits transits={transits} />
            <DashaTimeline chart={chart} tree={tree} />
            <Remedies remedies={remedies} />
            <Synastry profiles={profiles} selectedId={selectedId} />
          </>
        )}
      </main>
    </div>
  )
}

export { LifeStages, DashaTimeline }
