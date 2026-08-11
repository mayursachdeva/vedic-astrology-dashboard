import { useEffect, useState } from 'react'
import { createProfile, searchPlaces } from '../api.js'

function PlaceField({ value, onPick, onClear }) {
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState([])
  const [searching, setSearching] = useState(false)

  // Debounced so typing does not fire a lookup per keystroke. The search is local, but
  // there is no reason to run it five times for one word.
  useEffect(() => {
    if (value || query.trim().length < 2) {
      setOptions([])
      return undefined
    }
    const timer = setTimeout(async () => {
      setSearching(true)
      try {
        const found = await searchPlaces(query)
        setOptions(found.results)
      } catch {
        setOptions([])
      } finally {
        setSearching(false)
      }
    }, 200)
    return () => clearTimeout(timer)
  }, [query, value])

  if (value) {
    return (
      <div className="place chosen">
        <span>
          {value.label}
          <small>
            {value.latitude.toFixed(4)}, {value.longitude.toFixed(4)} · {value.timezone}
          </small>
        </span>
        <button type="button" onClick={() => { onClear(); setQuery(''); setOptions([]) }}>
          change
        </button>
      </div>
    )
  }

  return (
    <div className="place">
      <input
        placeholder="Birth place — start typing"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        autoComplete="off"
      />
      {searching && <p className="footnote">searching…</p>}
      {options.length > 0 && (
        <ul className="place-options">
          {options.map((place) => (
            <li key={`${place.label}-${place.latitude}-${place.longitude}`}>
              <button type="button" onClick={() => onPick(place)}>
                {place.label}
                <small>
                  {place.latitude.toFixed(3)}, {place.longitude.toFixed(3)}
                  {place.population > 0 && ` · pop. ${place.population.toLocaleString()}`}
                </small>
              </button>
            </li>
          ))}
        </ul>
      )}
      {query.trim().length >= 2 && !searching && options.length === 0 && (
        <p className="footnote">
          Nothing found. Try the nearest town, or add the country —
          “Porbandar, India”.
        </p>
      )}
    </div>
  )
}


function ProfileForm({ onCreated }) {
  const [form, setForm] = useState({
    name: '',
    birth_local: '',
    relation: '',
    time_confidence: 'to_the_minute',
  })
  const [place, setPlace] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const update = (field) => (event) =>
    setForm({ ...form, [field]: event.target.value })

  async function submit(event) {
    event.preventDefault()
    if (!place) {
      setError('Choose a birth place so the coordinates can be filled in.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const created = await createProfile({
        ...form,
        place: place.label,
        latitude: place.latitude,
        longitude: place.longitude,
        // GeoNames names the zone for the place itself, which is a firmer answer than
        // deriving it from the coordinates.
        timezone_name: place.timezone || null,
      })
      setForm({ ...form, name: '', birth_local: '' })
      setPlace(null)
      onCreated(created)
    } catch (problem) {
      setError(problem.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="profile-form" onSubmit={submit}>
      <h3>Add a person</h3>
      <input required placeholder="Name" value={form.name} onChange={update('name')} />
      <input
        required
        type="datetime-local"
        step="1"
        value={form.birth_local}
        onChange={update('birth_local')}
      />
      <PlaceField value={place} onPick={setPlace} onClear={() => setPlace(null)} />
      <input
        placeholder="Relation (self, mother…)"
        value={form.relation}
        onChange={update('relation')}
      />
      <label>
        How sure is the birth time?
        <select value={form.time_confidence} onChange={update('time_confidence')}>
          <option value="exact">Exact</option>
          <option value="to_the_minute">To the minute</option>
          <option value="to_the_hour">To the hour</option>
          <option value="approximate">Approximate</option>
          <option value="unknown">Unknown</option>
        </select>
      </label>
      <button disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
      {error && <p className="error">{error}</p>}
    </form>
  )
}

export { ProfileForm }
