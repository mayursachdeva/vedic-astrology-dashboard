import { useEffect, useRef, useState } from 'react'
import { askStreaming } from '../api.js'
import { useGlossary } from '../glossary.js'
import { Formatted } from './Text.jsx'

// A conversation, not a single shot.
//
// It used to answer one question and stop. Every submission started a fresh exchange, so
// when an answer ended by offering to look at something else — which this model does
// constantly — there was no way to say yes. The reply arrived with no idea what "yes"
// referred to, and the previous answer had already been wiped off the screen.
//
// So the turns stay, the box stays, and each question is sent with the exchange so far.

// What each lookup is doing, in the reader's language. The tool names and julian day
// numbers are the model's business; someone waiting wants to know what is being checked.
const LOOKUPS = {
  get_planet: (input) => `Checking where ${input.body || 'a planet'} sits`,
  get_house: (input, houses) =>
    `Reading the house of ${houses[input.house] || 'the chart'} and its ruler`,
  get_dasha_at: () => 'Working out which chapter is running',
  get_life_stage: () => 'Reading what that chapter does to each part of life',
  get_transits_at: () => 'Checking where the planets are now',
  get_yogas: () => 'Looking for named combinations',
  search_scripture: (input) => `Searching the texts for “${input.term || ''}”`,
}

function describe(call, houses) {
  const phrase = LOOKUPS[call.tool]
  return phrase ? phrase(call.input || {}, houses) : `Looking up ${call.tool}`
}

function Answer({ turn }) {
  return (
    <div className="answer panel">
      {turn.warning && <p className="warnings">{turn.warning}</p>}
      <Formatted text={turn.answer} />
      <details className="technical">
        <summary>
          What it looked up ({turn.tool_calls.length} lookups, {turn.model})
        </summary>
        <ul>
          {turn.tool_calls.map((call, index) => (
            <li key={index}>
              <code>{call.tool}</code> {JSON.stringify(call.input)}
              {call.error && <span className="retro"> — failed</span>}
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}

function Ask({ profileId, profileName, initialQuestion = '' }) {
  const [question, setQuestion] = useState(initialQuestion)
  const [turns, setTurns] = useState([])
  const [lookups, setLookups] = useState([])
  const [text, setText] = useState('')
  const [asking, setAsking] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const foot = useRef(null)
  const box = useRef(null)
  const { houses } = useGlossary()

  // A different person is a different conversation.
  useEffect(() => {
    setTurns([])
    setText('')
    setLookups([])
    setAsking('')
    setError(null)
  }, [profileId])

  // Arriving from a page that suggested a question should land with it already typed.
  useEffect(() => {
    if (initialQuestion) setQuestion(initialQuestion)
  }, [initialQuestion])

  useEffect(() => {
    if (foot.current) foot.current.scrollIntoView({ block: 'nearest' })
  }, [text, lookups, turns.length, busy])

  async function submit(event) {
    event.preventDefault()
    const asked = question.trim()
    if (!asked || busy) return
    setBusy(true)
    setError(null)
    setText('')
    setLookups([])
    setAsking(asked)
    setQuestion('')
    let landed = false
    try {
      await askStreaming(
        profileId,
        asked,
        (message) => {
          if (message.type === 'lookup') {
            setLookups((current) => [...current, message])
            // Anything written before a lookup was the model talking itself towards it,
            // not the answer. The answer comes in the round that calls no tools.
            setText('')
          } else if (message.type === 'restart') setText('')
          else if (message.type === 'token') setText((current) => current + message.text)
          else if (message.type === 'answer') {
            landed = true
            setTurns((current) => [...current, { question: asked, ...message }])
            setText('')
            setLookups([])
            setAsking('')
          } else if (message.type === 'error') setError(message.message)
        },
        // Only the questions and the finished answers. The tool traffic would dwarf the
        // context, and the model is meant to look a fact up again rather than trust its
        // own earlier summary of it.
        turns.map((turn) => ({ question: turn.question, answer: turn.answer })),
      )
    } catch (problem) {
      setError(problem.message)
    } finally {
      setBusy(false)
      if (!landed) {
        // The box is cleared on send, so a failed question vanished with nothing to
        // retry — worst when the model has died, which is exactly when you want it
        // back. Put it where it was.
        setQuestion((typed) => typed || asked)
        setAsking('')
        setLookups([])
        setText('')
        setError((shown) => shown || 'That answer did not arrive. The question is back in the box.')
      }
      if (box.current) box.current.focus()
    }
  }

  return (
    <section className="ask">
      <div className="page-head">
        <div>
          <h2>Ask</h2>
          <p className="sub">
            Answered by a model running on this machine. It is given no chart data — it
            has to look every fact up, so it cannot invent a placement.
          </p>
        </div>
        {turns.length > 0 && (
          <button type="button" className="link" onClick={() => setTurns([])}>
            Start again
          </button>
        )}
      </div>

      <div className="thread">
        {turns.map((turn, index) => (
          <div key={index} className="turn">
            <p className="asked">{turn.question}</p>
            <Answer turn={turn} />
          </div>
        ))}

        {busy && (
          <div className="turn">
            <p className="asked">{asking}</p>
            <ol className="lookups panel">
              {lookups.map((call, index) => (
                <li key={index} className={call.error ? 'retro' : ''}>
                  {describe(call, houses || {})}
                  {call.error && ' — that one failed, trying again'}
                </li>
              ))}
              <li className="working">{text ? 'Writing the answer…' : 'Thinking…'}</li>
              {text && <li className="draft">{text}</li>}
            </ol>
          </div>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      <form onSubmit={submit} className="ask-form">
        <input
          ref={box}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={
            turns.length
              ? 'Reply, or ask something else…'
              : `Ask something about ${profileName}'s chart…`
          }
        />
        <button disabled={busy}>{busy ? 'Working…' : turns.length ? 'Send' : 'Ask'}</button>
      </form>
      {turns.length > 0 && !busy && (
        <p className="footnote">
          Replies carry the conversation with them, so “yes, do that” works.
        </p>
      )}
      <div ref={foot} />
    </section>
  )
}

export { Ask }
