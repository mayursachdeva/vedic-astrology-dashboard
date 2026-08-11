import { useState } from 'react'
import { useGlossary } from '../glossary.js'
import { corpusPassage } from '../api.js'

function Citation({ text, refer, located }) {
  const [passage, setPassage] = useState(null)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(false)

  if (!located || !refer || !refer.work) {
    return <p className="citation unverified">Source: {text}</p>
  }

  async function toggle() {
    if (open) { setOpen(false); return }
    setOpen(true)
    if (passage || error) return
    try {
      setPassage(await corpusPassage(refer))
    } catch (problem) {
      setError(problem.message)
    }
  }

  return (
    <div className="citation">
      <button type="button" className="cite-open" onClick={toggle}>
        Source: {text} {open ? '▴' : '▾'}
      </button>
      {open && (
        <div className="passage">
          {error && <p className="error">Could not load the passage: {error}</p>}
          {!passage && !error && <p className="footnote">loading…</p>}
          {passage && passage.passages.map((item, index) => (
            <blockquote key={index}>
              {item.heading && <strong>{item.heading}. </strong>}
              {item.text}
            </blockquote>
          ))}
        </div>
      )}
    </div>
  )
}


function Term({ children, name }) {
  const glossary = useGlossary()
  const key = String(name || children).toLowerCase()
  const definition = glossary.terms[key]?.definition
  if (!definition) return children
  return (
    <abbr className="term" title={definition}>
      {children}
    </abbr>
  )
}


function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}


function Formatted({ text }) {
  const blocks = []
  let bullets = []

  const inline = (line, key) => {
    const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={index}>{part.slice(2, -2)}</strong>
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={index}>{part.slice(1, -1)}</code>
      }
      return <span key={index}>{part}</span>
    })
  }

  const flush = () => {
    if (!bullets.length) return
    blocks.push(
      <ul key={`ul-${blocks.length}`}>
        {bullets.map((item, index) => <li key={index}>{inline(item)}</li>)}
      </ul>,
    )
    bullets = []
  }

  text.split(/\n/).forEach((raw) => {
    const line = raw.trim()
    if (!line) { flush(); return }
    const bullet = line.match(/^[-*]\s+(.*)$/)
    if (bullet) { bullets.push(bullet[1]); return }
    const heading = line.match(/^#{1,4}\s+(.*)$/)
    flush()
    if (heading) {
      blocks.push(<h4 key={blocks.length}>{inline(heading[1])}</h4>)
    } else {
      blocks.push(<p key={blocks.length} className="plain">{inline(line)}</p>)
    }
  })
  flush()
  return <>{blocks}</>
}

// A search result shows the excerpt around the match. Rendering the whole passage
// buried the searched-for word under thousands of characters of surrounding text.

export { Citation, Term, formatDate, Formatted }
