import { useEffect, useState } from 'react'
import { deleteProfile, listProfiles, startReading } from './api.js'
import { AREAS, useProfile } from './data.js'
import { ProfileForm } from './components/ProfileForm.jsx'
import { Ask } from './components/Ask.jsx'
import Home from './views/Home.jsx'
import Area from './views/Area.jsx'
import TimelineView from './views/TimelineView.jsx'
import Technical from './views/Technical.jsx'

// The whole dashboard used to be one 1,187-line component rendering thirteen sections
// into a single column. Nothing was prioritised, so everything competed. This is now
// just the shell: who you are looking at, where you are, and nothing else.

const VIEWS = [
  { key: 'home', label: 'Overview' },
  ...AREAS.map((area) => ({ key: `area:${area}`, label: area })),
  { key: 'timeline', label: 'The years ahead' },
  { key: 'technical', label: 'The chart itself' },
  { key: 'ask', label: 'Ask' },
]

export default function App() {
  const [profiles, setProfiles] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [view, setView] = useState('home')
  const [question, setQuestion] = useState('')
  const [openHouse, setOpenHouse] = useState(null)
  const [error, setError] = useState(null)

  const data = useProfile(selectedId)

  useEffect(() => {
    listProfiles()
      .then((loaded) => {
        setProfiles(loaded)
        if (loaded.length) setSelectedId((current) => current ?? loaded[0].id)
      })
      .catch((problem) => setError(problem.message))
  }, [])

  useEffect(() => { setView('home') }, [selectedId])

  const openArea = (area) => setView(`area:${area}`)
  // A house clicked anywhere opens where the room for it is.
  const openHouseAt = (house) => { setOpenHouse(house); setView('technical') }
  const ask = (prompt) => { setQuestion(prompt); setView('ask') }

  async function removeProfile(id) {
    await deleteProfile(id)
    const remaining = profiles.filter((profile) => profile.id !== id)
    setProfiles(remaining)
    if (selectedId === id) setSelectedId(remaining.length ? remaining[0].id : null)
  }

  const progress = data.reading?.progress
  const written = progress ? progress.written : 0
  const total = progress ? progress.total : 0

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

        {selectedId != null && (
          <nav className="views">
            {VIEWS.map((entry) => (
              <button
                key={entry.key}
                className={view === entry.key ? 'active' : ''}
                onClick={() => setView(entry.key)}
              >
                {entry.label}
              </button>
            ))}
          </nav>
        )}

        {selectedId != null && progress && !progress.complete && (
          <div className="reading-state">
            {progress.running ? (
              <p className="footnote">Writing the reading — {written} of {total} done.</p>
            ) : (
              <>
                <p className="footnote">
                  {written === 0
                    ? 'No written reading yet. The computed detail is all here either way.'
                    : `${written} of ${total} sections written.`}
                </p>
                <button
                  className="link"
                  onClick={async () => {
                    try {
                      await startReading(selectedId)
                      setTimeout(data.refreshReading, 3000)
                    } catch (problem) {
                      setError(problem.message)
                    }
                  }}
                >
                  Write the reading
                </button>
              </>
            )}
          </div>
        )}

        <ProfileForm
          onCreated={(created) => {
            setProfiles([...profiles, created])
            setSelectedId(created.id)
          }}
        />
      </aside>

      <main>
        {error && <p className="error">{error}</p>}
        {data.error && <p className="error">{data.error}</p>}
        {selectedId == null && !error && (
          <p className="plain">Add a person to see their chart.</p>
        )}

        {selectedId != null && view === 'home' && (
          <Home
            {...data}
            onOpenArea={openArea}
            onOpenTimeline={() => setView('timeline')}
            onOpenHouse={openHouseAt}
          />
        )}
        {selectedId != null && view.startsWith('area:') && (
          <Area area={view.slice(5)} {...data} onAsk={ask} />
        )}
        {selectedId != null && view === 'timeline' && (
          <TimelineView {...data} onOpenArea={openArea} />
        )}
        {selectedId != null && view === 'technical' && (
          <Technical
            {...data}
            profiles={profiles}
            selectedId={selectedId}
            onAsk={ask}
            openHouse={openHouse}
            onHouseShown={() => setOpenHouse(null)}
          />
        )}
        {selectedId != null && view === 'ask' && data.chart && (
          <Ask
            profileId={selectedId}
            profileName={data.chart.profile.name}
            initialQuestion={question}
          />
        )}
      </main>
    </div>
  )
}
