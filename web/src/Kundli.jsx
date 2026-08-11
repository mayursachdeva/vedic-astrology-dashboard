// North Indian kundli: a square with both diagonals and an inner rhombus, giving the
// twelve houses. Houses are fixed in place and the signs rotate with the lagna, which
// is what distinguishes this from the South Indian layout.

const SIZE = 400
const HALF = SIZE / 2

// Centroid of each house cell, house 1 at top centre then counter-clockwise.
const HOUSE_ANCHORS = [
  [200, 92],  // 1
  [104, 46],  // 2
  [50, 100],  // 3
  [96, 200],  // 4
  [50, 300],  // 5
  [104, 354], // 6
  [200, 308], // 7
  [296, 354], // 8
  [350, 300], // 9
  [304, 200], // 10
  [350, 100], // 11
  [296, 46],  // 12
]

const SHORT = {
  Sun: 'Su', Moon: 'Mo', Mars: 'Ma', Mercury: 'Me', Jupiter: 'Ju',
  Venus: 'Ve', Saturn: 'Sa', Rahu: 'Ra', Ketu: 'Ke',
}

export default function Kundli({ title, lagnaSign, bodies, onSelectHouse, selectedHouse }) {
  // bodies: { Sun: { house, sign, retrograde, label } }
  const byHouse = {}
  for (let house = 1; house <= 12; house += 1) byHouse[house] = []
  Object.entries(bodies).forEach(([body, info]) => {
    byHouse[info.house].push({ body, ...info })
  })

  return (
    <figure className="kundli">
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`${title} chart`}>
        <rect x="1" y="1" width={SIZE - 2} height={SIZE - 2} className="frame" />
        <line x1="0" y1="0" x2={SIZE} y2={SIZE} className="frame" />
        <line x1={SIZE} y1="0" x2="0" y2={SIZE} className="frame" />
        <polygon
          points={`${HALF},0 ${SIZE},${HALF} ${HALF},${SIZE} 0,${HALF}`}
          className="frame"
        />

        {HOUSE_ANCHORS.map(([x, y], index) => {
          const house = index + 1
          const sign = ((lagnaSign + index) % 12) + 1
          const occupants = byHouse[house]
          const isSelected = selectedHouse === house
          return (
            <g
              key={house}
              className={[
                'house',
                isSelected ? 'selected' : '',
                onSelectHouse ? 'clickable' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => onSelectHouse && onSelectHouse(house)}
            >
              {/* A cell with only a numeral and two glyphs in it has almost no area to
                  hit. This invisible disc is what makes the whole cell clickable. */}
              {onSelectHouse && (
                <circle cx={x} cy={y - 6} r="44" className="house-hit" />
              )}
              <text x={x} y={y - 22} className="sign-number">{sign}</text>
              {occupants.map((occupant, position) => (
                <text
                  key={occupant.body}
                  x={x}
                  y={y - 2 + position * 15}
                  className={`graha${occupant.retrograde ? ' retrograde' : ''}`}
                >
                  {SHORT[occupant.body] || occupant.body}
                  {occupant.retrograde ? 'ᴿ' : ''}
                </text>
              ))}
            </g>
          )
        })}
      </svg>
    </figure>
  )
}
