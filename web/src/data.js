import { useEffect, useState } from 'react'
import {
  getChart,
  getDashas,
  getLifeStages,
  getPanchanga,
  getReading,
  getRemedies,
  getTransits,
} from './api.js'

// One fetch of everything a person's views need, shared across them. Previously each
// section fetched for itself inside one enormous component; with views that would mean
// refetching the whole chart every time you moved between pages.
export function useProfile(profileId) {
  const [data, setData] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (profileId == null) {
      setData({})
      return undefined
    }
    let cancelled = false
    setLoading(true)
    setError(null)

    const load = async () => {
      try {
        // The chart is what every view needs first, so it is awaited on its own and
        // the slower pieces fill in behind it.
        const chart = await getChart(profileId, '1,9,10')
        if (cancelled) return
        setData((current) => ({ ...current, chart }))

        const [stages, reading, remedies, panchanga, transits, tree] = await Promise.all([
          getLifeStages(profileId, 12).catch(() => null),
          getReading(profileId).catch(() => null),
          getRemedies(profileId).catch(() => null),
          getPanchanga(profileId).catch(() => null),
          getTransits(profileId, 36).catch(() => null),
          getDashas(profileId, 2).catch(() => null),
        ])
        if (cancelled) return
        setData({ chart, stages, reading, remedies, panchanga, transits, tree })
      } catch (problem) {
        if (!cancelled) setError(problem.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [profileId])

  const refreshReading = async () => {
    const reading = await getReading(profileId).catch(() => null)
    setData((current) => ({ ...current, reading }))
  }

  return { ...data, loading, error, refreshReading }
}

// The section of the written reading matching a view, if it has been written yet.
export function section(reading, key) {
  if (!reading) return null
  const found = reading.sections.find((item) => item.key === key)
  return found && found.status === 'ok' && found.body ? found : null
}

export const AREAS = [
  'Career',
  'Relationships',
  'Health',
  'Finance',
  'Family',
  'Learning',
]
