import { useEffect, useState } from 'react'
import { getGlossary } from './api.js'

// The interface used to carry its own hand-written glossary, which could drift from the
// one the generated prose is held to. There is one now, on the server, and this fetches
// it once and shares it.
const EMPTY = { terms: {}, houses: {}, dignities: {} }
let cache = null
const waiting = []

export function useGlossary() {
  const [glossary, setGlossary] = useState(cache || EMPTY)

  useEffect(() => {
    if (cache) return undefined
    let cancelled = false
    waiting.push((value) => { if (!cancelled) setGlossary(value) })
    if (waiting.length === 1) {
      getGlossary()
        .then((value) => {
          cache = value
          waiting.splice(0).forEach((notify) => notify(value))
        })
        .catch(() => waiting.splice(0).forEach((notify) => notify(EMPTY)))
    }
    return () => { cancelled = true }
  }, [])

  return glossary
}

export const DOMAIN_HOUSES = {
  Career: [10, 6, 2],
  Relationships: [7, 5, 11],
  Health: [1, 6, 8],
  Finance: [2, 11, 9],
  Family: [4, 2, 3],
  Learning: [5, 9, 4],
}
