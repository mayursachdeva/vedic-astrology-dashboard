import { useEffect, useMemo, useState } from 'react'
import Kundli from '../Kundli.jsx'
import { Ashtakavarga, Karakas, PositionsTable, Shadbala, Yogas } from '../components/Findings.jsx'
import { DashaTimeline } from '../components/Timeline.jsx'
import { Panchanga, Transits } from '../components/Sky.jsx'
import { Synastry } from '../components/Synastry.jsx'
import { Library } from '../components/Library.jsx'
import { HouseReading } from '../components/House.jsx'
import { Panel } from '../components/Panel.jsx'

const VARGAS = ['D1', 'D9', 'D10']
// The two the house reading is defined for. D10 has no bhava reading of its own.
const READABLE = ['D1', 'D9']

// Everything that assumes the vocabulary, gathered in one place instead of scattered
// through the reading. Nobody has to come here, and anyone checking the work can.
//
// It used to be nine sections in one scroll with nothing between them, so finding the
// ashtakavarga meant scrolling past the yogas every time. Each is now a box with an
// anchor, and the chart sits in a rail that stays put while you read the rest.
const SECTIONS = [
  { id: 'positions', label: 'Positions' },
  { id: 'yogas', label: 'Combinations' },
  { id: 'support', label: 'House support' },
  { id: 'strength', label: 'Planet strength' },
  { id: 'karakas', label: 'Roles' },
  { id: 'day', label: 'The day' },
  { id: 'transits', label: 'Transits' },
  { id: 'periods', label: 'Periods' },
  { id: 'compare', label: 'Compare' },
]

export default function Technical({
  chart, tree, transits, panchanga, profiles, selectedId, onAsk,
  openHouse, onHouseShown,
}) {
  const [varga, setVarga] = useState('D1')
  const [house, setHouse] = useState(null)

  // A house clicked on the overview arrives here, because this is where there is room
  // to answer it.
  useEffect(() => {
    if (openHouse == null) return
    setHouse(openHouse)
    setVarga('D1')
    onHouseShown?.()
  }, [openHouse, onHouseShown])

  if (!chart) return <p className="plain">Loading…</p>

  const bodies = useMemo(() => {
    if (varga === 'D1') {
      return Object.fromEntries(
        Object.entries(chart.positions).map(([body, position]) => [
          body,
          { house: position.house, sign: position.sign, retrograde: position.retrograde },
        ]),
      )
    }
    const table = chart.vargas[varga]
    return Object.fromEntries(
      Object.entries(table.signs).map(([body, info]) => [
        body,
        { house: info.house, sign: info.sign, retrograde: chart.positions[body].retrograde },
      ]),
    )
  }, [chart, varga])

  const lagnaSign = varga === 'D1' ? chart.lagna.sign : chart.vargas[varga].lagna_sign

  return (
    <div className="technical-view">
      <div className="page-head">
        <div>
          <h2>The chart itself</h2>
          <p className="sub">
            The computed detail behind everything else, in the vocabulary the texts use.
          </p>
        </div>
        <nav className="jump">
          {SECTIONS.map((entry) => (
            <a key={entry.id} href={`#${entry.id}`}>{entry.label}</a>
          ))}
        </nav>
      </div>

      <div className="tech-grid">
        <aside className="tech-rail">
          <Panel
            title={varga === 'D1' ? 'Birth chart' : chart.vargas[varga].name}
            meta={varga === 'D1' ? `${chart.lagna.sign_name} rising` : varga}
          >
            <nav className="tabs">
              {VARGAS.map((name) => (
                <button
                  key={name}
                  className={name === varga ? 'active' : ''}
                  onClick={() => setVarga(name)}
                >
                  {name === 'D1' ? 'Birth' : chart.vargas[name].name}
                </button>
              ))}
            </nav>
            <Kundli
              title=""
              lagnaSign={lagnaSign}
              bodies={bodies}
              // Houses open in both, since the ninth-part chart has the same twelve
              // subjects read a second way. The tenth-part chart has no house reading.
              onSelectHouse={READABLE.includes(varga)
                ? (picked) => setHouse(house === picked ? null : picked)
                : undefined}
              selectedHouse={house}
            />
            {house == null && (
              <p className="footnote">
                {READABLE.includes(varga)
                  ? 'Tap any house to read it in full.'
                  : 'The tenth-part chart has no house reading of its own.'}
              </p>
            )}
          </Panel>
        </aside>

        <div className="tech-main">
          {/* A house reading takes the column to itself. Leaving the eight tables
              underneath it made the page nine thousand pixels tall, so opening a house
              meant scrolling past everything else to get back out of it. */}
          {house != null ? (
            <HouseReading
              profileId={selectedId}
              house={house}
              varga={varga}
              onAsk={onAsk}
              onClose={() => setHouse(null)}
            />
          ) : (
          <>
          {/* Only this one takes a title: the rest render their own heading, and a
              Panel title on top of that read as the same word twice. */}
          <Panel className="anchored" title="Positions"><span id="positions" />
            <PositionsTable chart={chart} />
          </Panel>
          <Panel className="anchored"><span id="yogas" />
            <Yogas chart={chart} />
          </Panel>
          <Panel className="anchored"><span id="support" />
            <Ashtakavarga chart={chart} />
          </Panel>
          <Panel className="anchored"><span id="strength" />
            <Shadbala chart={chart} />
          </Panel>
          <Panel className="anchored"><span id="karakas" />
            <Karakas chart={chart} />
          </Panel>
          <Panel className="anchored"><span id="day" />
            <Panchanga panchanga={panchanga} />
          </Panel>
          <Panel className="anchored"><span id="transits" />
            <Transits transits={transits} />
          </Panel>
          <Panel className="anchored"><span id="periods" />
            <DashaTimeline chart={chart} tree={tree} />
          </Panel>
          <Panel className="anchored"><span id="compare" />
            <Synastry profiles={profiles} selectedId={selectedId} />
          </Panel>
          <Library />
          </>
          )}
        </div>
      </div>
    </div>
  )
}
