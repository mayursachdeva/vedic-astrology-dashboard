import { useEffect, useMemo, useState } from 'react'
import { getHouse } from '../api.js'
import { Panel, Verdict } from './Panel.jsx'
import { Passage } from './Passage.jsx'

// One house, read a step at a time.
//
// Everything here used to be one column: significations, the sign, the ruler, every
// occupant with its star and its verses, the strength tables, then the remedies. Three
// screens and six hundred words, which is a wall however good the material is.
//
// So it is five steps of about a screen each, in the order the questions actually
// arrive: what this part of life is, who runs it, who stands in it, whether it is
// working, and what to do about it. A step opens once the one before it has been read —
// not to be coy, but because "what to do" means nothing before "how is it doing", and
// handing over remedies first is what makes a reading feel like a shop.

const STANDING = {
  'well placed': 'supported',
  'under pressure': 'mixed',
  'poorly placed': 'under strain',
}

const VERDICT = {
  working: 'supported',
  mixed: 'mixed',
  'needs work': 'under strain',
  quiet: 'mixed',
}

function ordinal(n) {
  const suffix = ['th', 'st', 'nd', 'rd'][n % 100 > 10 && n % 100 < 14 ? 0 : n % 10] || 'th'
  return `${n}${suffix}`
}

/** One labelled fact. Several of these read faster than the sentence they replace. */
function Fact({ label, children }) {
  return (
    <div className="fact">
      <span className="fact-label">{label}</span>
      <span className="fact-value">{children}</span>
    </div>
  )
}

// --- the five steps ----------------------------------------------------------

function Subject({ data }) {
  return (
    <>
      <h4>What this house is read for</h4>
      <Passage block={data.represents} />
      <h4>Its sign — {data.sign_name}</h4>
      <Passage block={data.sign_says} />
    </>
  )
}

function Ruler({ data }) {
  const lord = data.lord
  return (
    <>
      <p className="plain">
        <strong>{lord.name}</strong> rules this house from the{' '}
        {ordinal(lord.sits_in_house)}, standing in {lord.sits_in_sign}, where it{' '}
        {lord.plain}.
        {lord.vargottama && (
          <> It holds the same sign in both charts (vargottama), read as steadiness.</>
        )}
      </p>
      <p className="footnote">Its own standing: {STANDING[lord.standing]}.</p>
      {lord.says ? (
        <Passage block={lord.says} />
      ) : (
        <p className="footnote">
          The chapter that tabulates this placement is missing that verse in the edition
          here, so there is nothing to quote for it.
        </p>
      )}
    </>
  )
}

function Occupants({ data, onAsk }) {
  if (!data.occupants.length) {
    return (
      <p className="plain">
        Nobody stands here. An empty house is not a quiet one — it is read through its
        ruler, on the step before this. Most houses in most charts are empty.
      </p>
    )
  }
  return data.occupants.map((occupant) => (
    <article key={occupant.body} className="occupant">
      <header>
        <h4>{occupant.body}</h4>
        <Verdict verdict={STANDING[occupant.standing]} />
      </header>

      <div className="facts">
        <Fact label="Where">{occupant.sign} {occupant.degree}°</Fact>
        <Fact label="Condition">{occupant.plain}</Fact>
        {occupant.strength && (
          <Fact label="Strength">
            {Math.round(occupant.strength.ratio * 100)}% of what it needs
          </Fact>
        )}
        {occupant.avastha && <Fact label="Delivers">{occupant.avastha.delivers}</Fact>}
        <Fact label="Star">
          {occupant.nakshatra.name}, quarter {occupant.nakshatra.pada}
        </Fact>
        {occupant.varga_class && (
          <Fact label="This ninth">{occupant.varga_class.plain}</Fact>
        )}
      </div>

      {(occupant.vargottama || occupant.retrograde || occupant.combust) && (
        <p className="footnote">
          {occupant.vargottama && 'Same sign in both charts (vargottama). '}
          {occupant.retrograde && 'Moving backwards. '}
          {occupant.combust && 'Lost in the Sun (combust).'}
        </p>
      )}

      <details className="source">
        <summary>Its star, and what that means</summary>
        <Passage block={occupant.nakshatra.says} />
      </details>

      {occupant.classical.length > 0 && (
        <details className="source">
          <summary>
            What the texts say of {occupant.body} here ({occupant.classical.length})
          </summary>
          {occupant.classical.map((verse) => (
            <Passage key={verse.citation} block={verse} />
          ))}
        </details>
      )}

      {onAsk && (
        <button
          type="button"
          className="link"
          onClick={() => onAsk(
            `What does ${occupant.body} in my ${ordinal(data.house)} house mean?`,
          )}
        >
          Ask about this placement →
        </button>
      )}
    </article>
  ))
}

function Standing({ data }) {
  const watchers = data.aspected_by.length
    ? data.aspected_by.map((a) => a.body).join(', ')
    : 'nothing'
  return (
    <>
      <div className="verdict-line">
        <Verdict verdict={VERDICT[data.verdict]} />
        <span>{data.because.join('; ')}.</span>
      </div>

      <div className="facts">
        {data.support && (
          <Fact label="Chart support">
            {data.support.points} of {data.support.of} — {data.support.reading}
          </Fact>
        )}
        {data.strength && (
          <Fact label="Six-fold strength">
            {data.strength.rupas} rupas, {data.strength.reading}
          </Fact>
        )}
        <Fact label="Looked at by">{watchers}</Fact>
      </div>

      {data.strength && (
        <details className="source">
          <summary>Where that strength comes from</summary>
          <dl className="parts">
            {Object.entries(data.strength.parts).map(([name, value]) => (
              <div key={name}><dt>{name}</dt><dd>{value}</dd></div>
            ))}
          </dl>
        </details>
      )}

      {!data.support && (
        <p className="footnote">
          Chart support and six-fold strength are defined on the birth chart, so they are
          left out here rather than computed from a chart the texts never meant them for.
        </p>
      )}
    </>
  )
}

function Doing({ data }) {
  return (
    <>
      <p className="footnote">
        Given as the texts give them. Nothing here is medical, legal or financial advice,
        and none of it replaces any.
      </p>
      {data.remedies.map((entry) => (
        <article key={entry.body} className="remedy">
          <header>
            <h4>{entry.body}</h4>
            {entry.indicated && <em>attend to this one first</em>}
          </header>
          {entry.indicated && entry.because.length > 0 && (
            <p className="footnote">Because {entry.because.join('; ')}.</p>
          )}

          {entry.conduct && (
            <>
              <p className="label">
                How to behave
                {data.varga !== 'D1' && <em> — for where it stands in the birth chart</em>}
              </p>
              <Passage block={entry.conduct} />
            </>
          )}

          {entry.mantra && (
            <>
              <p className="label">What to recite</p>
              <p className="mantra">{entry.mantra}</p>
              <details className="source">
                <summary>How often, and with what</summary>
                <Passage block={entry.practice} />
              </details>
            </>
          )}

          {entry.profile && (
            <p className="footnote">
              Deity, colour and what is given away: {entry.profile.text}.
            </p>
          )}
        </article>
      ))}
    </>
  )
}

// --- the reader --------------------------------------------------------------

export function HouseReading({ profileId, house, varga, onClose, onAsk }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [step, setStep] = useState(0)
  const [reached, setReached] = useState(0)

  useEffect(() => {
    let cancelled = false
    setData(null)
    setError(null)
    setStep(0)
    setReached(0)
    getHouse(profileId, house, varga)
      .then((loaded) => { if (!cancelled) setData(loaded) })
      .catch((problem) => { if (!cancelled) setError(problem.message) })
    return () => { cancelled = true }
  }, [profileId, house, varga])

  const steps = useMemo(() => (data ? [
    { key: 'subject', label: 'What it is', render: () => <Subject data={data} /> },
    { key: 'ruler', label: 'Who runs it', render: () => <Ruler data={data} /> },
    {
      key: 'in',
      label: data.occupants.length
        ? `Who is in it (${data.occupants.length})`
        : 'Who is in it',
      render: () => <Occupants data={data} onAsk={onAsk} />,
    },
    { key: 'doing', label: 'How it is doing', render: () => <Standing data={data} /> },
    { key: 'todo', label: 'What to do', render: () => <Doing data={data} /> },
  ] : []), [data, onAsk])

  if (error) return <Panel title={`House ${house}`}><p className="error">{error}</p></Panel>
  if (!data) return <Panel title={`House ${house}`}><p className="plain">Reading…</p></Panel>

  const go = (index) => {
    setStep(index)
    setReached((furthest) => Math.max(furthest, index))
  }
  const current = steps[step]
  const last = step === steps.length - 1

  return (
    <div className="house-reading">
      <Panel
        tier={1}
        title={`${varga === 'D1' ? 'House' : `${varga} house`} ${data.house} — ${data.means}`}
        meta={<button className="link" onClick={onClose}>close</button>}
      >
        <p className="headline">{data.headline}</p>
        {data.read_for && (
          <p className="footnote">
            {data.read_for.sentence} <span className="cite">{data.read_for.citation}</span>
          </p>
        )}
      </Panel>

      <nav className="steps" aria-label="Steps through this house">
        {steps.map((entry, index) => {
          // One step ahead of the furthest reached stays open, so the next move is
          // always obvious; anything past that waits its turn.
          const locked = index > reached + 1
          return (
            <button
              key={entry.key}
              type="button"
              className={[
                index === step ? 'here' : '',
                index <= reached ? 'read' : '',
                locked ? 'locked' : '',
              ].filter(Boolean).join(' ')}
              disabled={locked}
              title={locked ? 'Read the step before this one first' : undefined}
              onClick={() => !locked && go(index)}
            >
              <span className="n">{locked ? '·' : index + 1}</span>
              {entry.label}
            </button>
          )
        })}
      </nav>

      <Panel title={current.label} meta={`step ${step + 1} of ${steps.length}`}>
        {current.render()}
      </Panel>

      <div className="step-nav">
        <button
          type="button"
          className="link"
          disabled={step === 0}
          onClick={() => go(step - 1)}
        >
          ← {step > 0 ? steps[step - 1].label : 'Back'}
        </button>
        {last ? (
          <button type="button" className="primary" onClick={onClose}>
            Done — close this house
          </button>
        ) : (
          <button type="button" className="primary" onClick={() => go(step + 1)}>
            {steps[step + 1].label} →
          </button>
        )}
      </div>
    </div>
  )
}
