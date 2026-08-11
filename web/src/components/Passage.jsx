import { useState } from 'react'
import { Citation } from './Text.jsx'

// A quotation from the texts, opened one sentence at a time.
//
// These passages are long — a sign description runs to four hundred characters, a
// nakshatra's to three hundred — and five of them stacked is the wall this reading had
// become. The first sentence carries most of the sense, so that is what shows; the rest
// is one tap away and the citation stays visible either way.

const refer = (block) => block && ({
  work: block.work, chapter: block.chapter, verse: block.verse, page: block.page,
})

/** The first sentence, or a little more if the first one is very short. */
function lead(text) {
  const stops = []
  const pattern = /[.?!]\s/g
  let found = pattern.exec(text)
  while (found && stops.length < 4) {
    stops.push(found.index + 1)
    found = pattern.exec(text)
  }
  const cut = stops.find((at) => at >= 90) ?? stops[stops.length - 1] ?? text.length
  return cut >= text.length - 20 ? [text, ''] : [text.slice(0, cut), text.slice(cut).trim()]
}

export function Passage({ block, className = '' }) {
  const [open, setOpen] = useState(false)
  if (!block?.text) return null
  const [first, rest] = lead(block.text)

  return (
    <div className={`passage ${className}`.trim()}>
      <p className="plain">
        {open || !rest ? block.text : first}
        {rest && (
          <button type="button" className="more" onClick={() => setOpen(!open)}>
            {open ? ' less' : ' …more'}
          </button>
        )}
      </p>
      <Citation text={block.citation} refer={refer(block)} located />
    </div>
  )
}

export { refer }
