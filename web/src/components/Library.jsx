import { useEffect, useState } from 'react'
import { corpusSearch, corpusWorks } from '../api.js'

function Hit({ hit }) {
  const [full, setFull] = useState(false)
  const longer = hit.text.length > hit.excerpt.length + 20
  return (
    <li>
      <p className="citation">{hit.citation}</p>
      <blockquote>
        {hit.heading && <strong>{hit.heading}. </strong>}
        {full ? hit.text : hit.excerpt}
      </blockquote>
      {longer && (
        <button type="button" className="cite-open" onClick={() => setFull(!full)}>
          {full ? 'show less' : 'show the whole passage'}
        </button>
      )}
    </li>
  )
}


function Library() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [works, setWorks] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    corpusWorks().then(setWorks).catch(() => setWorks([]))
  }, [])

  async function submit(event) {
    event.preventDefault()
    if (query.trim().length < 2) return
    setBusy(true)
    try {
      setResults(await corpusSearch(query))
    } catch {
      setResults({ results: [] })
    } finally {
      setBusy(false)
    }
  }

  const total = works.reduce((sum, work) => sum + work.passages, 0)

  // Collapsed by default and framed as a checking tool rather than a feature. A raw
  // keyword search over 22 classical texts only helps someone who already knows what
  // to type, which is the opposite of who this dashboard is for. It is here so that a
  // claim can be audited against its source, not so anyone learns astrology from it.
  return (
    <details className="library">
      <summary>
        Check the sources — {total.toLocaleString()} passages from {works.length} works
      </summary>

      <p className="plain">
        Everything the dashboard says comes from these texts. Search them here to check
        a claim against the original wording. You do not need this to read your chart:
        the source behind any finding opens directly from the finding itself.
      </p>

      <form className="ask-form" onSubmit={submit}>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="A yoga, a planet, a remedy…"
        />
        <button disabled={busy}>{busy ? 'Searching…' : 'Search'}</button>
      </form>

      {results && (
        results.results.length === 0
          ? <p className="plain">Nothing found for “{results.query}”.</p>
          : <ul className="hits">
              {results.results.map((hit, index) => (
                <Hit key={index} hit={hit} />
              ))}
            </ul>
      )}

      <details className="technical">
        <summary>What is in the library</summary>
        <ul>
          {works.map((work) => (
            <li key={work.work}>
              {work.work} — {work.passages.toLocaleString()} passages
              {work.versified ? ', cited by chapter and verse' : ', cited by page'}
            </li>
          ))}
        </ul>
      </details>
    </details>
  )
}

export { Library }
