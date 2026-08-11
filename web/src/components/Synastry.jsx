import { useEffect, useState } from 'react'
import { getSynastry } from '../api.js'

function Synastry({ profiles, selectedId }) {
  const others = profiles.filter((p) => p.id !== selectedId)
  const [withId, setWithId] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setResult(null)
    setWithId('')
  }, [selectedId])

  if (others.length === 0) return null

  async function compare(id) {
    setWithId(id)
    setResult(null)
    setError(null)
    if (!id) return
    try {
      setResult(await getSynastry(selectedId, Number(id)))
    } catch (problem) {
      setError(problem.message)
    }
  }

  return (
    <section className="synastry">
      <h3>Compatibility</h3>
      <label className="compare-picker">
        Compare with{' '}
        <select value={withId} onChange={(e) => compare(e.target.value)}>
          <option value="">choose a person…</option>
          {others.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </label>

      {error && <p className="error">{error}</p>}

      {result && (
        <>
          <p className="plain score-line">
            <strong>{result.total} of {result.maximum}</strong> — {result.verdict}
          </p>
          <p className="footnote">{result.note}</p>

          <table className="positions">
            <caption>The eight factors</caption>
            <thead>
              <tr><th>Factor</th><th>Points</th><th>Why</th></tr>
            </thead>
            <tbody>
              {result.kutas.map((k) => (
                <tr key={k.name}>
                  <td>
                    {k.name}
                    {k.precision === 'simplified' && (
                      <abbr className="term" title={k.caveat}> ~</abbr>
                    )}
                  </td>
                  <td>{k.points} / {k.maximum}</td>
                  <td>{k.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {result.doshas.length > 0 && (
            <>
              <h4>Afflictions checked</h4>
              <ul className="yoga-list">
                {result.doshas.map((d) => (
                  <li key={d.name} className={d.present ? 'malefic' : 'benefic'}>
                    <p className="plain">
                      <strong>{d.name}:</strong>{' '}
                      {d.present ? 'present' : 'not counted against the match'}. {d.reason}.
                      {d.cancelled_by && ` ${d.cancelled_by}`}
                    </p>
                  </li>
                ))}
              </ul>
            </>
          )}

          <details className="technical">
            <summary>What this text actually says about partnership</summary>
            {Object.entries(result.seventh_house).map(([name, r]) => (
              <p key={name}>
                <strong>{name}</strong> — 7th house in {r.sign}, ruled by {r.lord} in the{' '}
                {r.lord_house} ({r.lord_dignity}); Venus in the {r.venus_house} ({r.venus_dignity}).
                Support: {r.support} points. <em>{r.citation}</em>
              </p>
            ))}
          </details>
        </>
      )}
    </section>
  )
}

export { Synastry }
