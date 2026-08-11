"""Composition root: profile in, dashboard payload out.

`core/` modules are deliberately unaware of each other and of storage. This is the one
place that wires them together, so the API layer stays a thin translation to HTTP and
the wiring itself is testable without a server.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import swisseph as swe

from astro.core import dasha as dasha_module
from astro.core.ashtakavarga import SAV_STRONG, SAV_WEAK, reduced_ashtakavarga
from astro.core.dasha import DashaPeriod, balance_at_birth, chain_at, vimshottari
from astro.core.ephemeris import SIGNS, Chart, compute_chart, julian_day
from astro.core.facts import ChartFacts, build_facts
from astro.core.timeloc import BirthMoment, resolve
from astro.core.varga import SHODASAVARGA, varga_chart
from astro.core.transit import (
    combustion_windows,
    confluence,
    contacts,
    gochara,
    retrograde_windows,
    sade_sati,
)
from astro.core.panchanga import compute as compute_panchanga
from astro.core.panchanga import day_span
from astro.core.shadbala import payload as shadbala_payload_of
from astro.core.karaka import payload as karaka_payload
from astro.core.shadbala import shadbala
from astro.core.synastry import match, seventh_house_reading
from astro.interpret.glossary import plainly
from astro.interpret.life_stages import DOMAINS, life_stages
from astro.interpret.remedies import remedies_payload
from astro.rules.engine import Rule, apply_rules, load_rules
from astro.store import Profile

# Shown on the dashboard by default. The rest of the shodasavarga stay available on
# request rather than cluttering the first screen.
DEFAULT_VARGAS = (1, 9, 10)


@dataclass(frozen=True)
class NatalChart:
    """Everything derived from one profile's birth moment."""

    profile: Profile
    moment: BirthMoment
    chart: Chart
    dashas: tuple[DashaPeriod, ...]
    facts: ChartFacts


# Rule files are read once. They are static data, and reloading them per request would
# turn every chart view into a directory scan.
_RULES: list[Rule] | None = None


def rules() -> list[Rule]:
    global _RULES
    if _RULES is None:
        _RULES = load_rules()
    return _RULES


def build_natal_chart(profile: Profile, *, dasha_depth: int = 3) -> NatalChart:
    moment = resolve(
        profile.birth_local,
        profile.latitude,
        profile.longitude,
        timezone_name=profile.timezone_name,
        use_true_lmt=profile.use_true_lmt,
    )
    chart = compute_chart(
        moment.jd_ut,
        profile.latitude,
        profile.longitude,
        ayanamsa=profile.ayanamsa,
        house_system=profile.house_system,
        node_type=profile.node_type,
    )
    dashas = vimshottari(
        chart.positions["Moon"].longitude, moment.jd_ut, depth=dasha_depth
    )
    return NatalChart(
        profile=profile,
        moment=moment,
        chart=chart,
        dashas=dashas,
        facts=build_facts(chart),
    )


def jd_to_iso(jd: float) -> str:
    """Julian Day (UT) to an ISO timestamp, for display and JSON."""
    year, month, day, hour = swe.revjul(jd, swe.GREG_CAL)
    total_seconds = round(hour * 3600)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    # revjul can hand back 24:00:00 after rounding; let datetime normalise it.
    base = datetime(year, month, day)
    return (base + timedelta(hours=hours, minutes=minutes, seconds=seconds)).isoformat()


def now_jd() -> float:
    now = datetime.now(UTC)
    return julian_day(
        now.year,
        now.month,
        now.day,
        now.hour + now.minute / 60.0 + now.second / 3600.0,
    )


def _period_payload(period: DashaPeriod, *, include_children: bool) -> dict:
    payload = {
        "lord": period.lord,
        "level": period.level,
        "level_name": period.level_name,
        "start": jd_to_iso(period.start_jd),
        "end": jd_to_iso(period.end_jd),
        "start_jd": period.start_jd,
        "end_jd": period.end_jd,
        "years": round(period.duration_days / dasha_module.JULIAN_YEAR_DAYS, 4),
    }
    if include_children:
        payload["children"] = [
            _period_payload(child, include_children=True) for child in period.children
        ]
    return payload


def chart_payload(
    natal: NatalChart,
    *,
    vargas: tuple[int, ...] = DEFAULT_VARGAS,
    at_jd: float | None = None,
) -> dict:
    """The JSON the dashboard renders.

    `at_jd` selects the moment used for "current dasha"; it defaults to now, and is a
    parameter so tests are not time-dependent.
    """
    chart = natal.chart
    moment = natal.moment
    moon = chart.positions["Moon"]
    reference_jd = now_jd() if at_jd is None else at_jd

    balance_lord, balance_years = balance_at_birth(moon.longitude)
    current = chain_at(natal.dashas, reference_jd)

    return {
        "profile": natal.profile.as_dict(),
        "birth": {
            "local": moment.local_datetime.isoformat(),
            "utc": moment.utc_datetime.isoformat(),
            "timezone": moment.timezone_name,
            "offset": moment.offset_label,
            "basis": moment.basis,
            "julian_day": moment.jd_ut,
            "warnings": list(moment.warnings),
        },
        "settings": {
            "ayanamsa": chart.ayanamsa,
            "ayanamsa_value": chart.ayanamsa_value,
            "node_type": chart.node_type,
            "house_system": chart.house_system,
            "time_confidence": natal.profile.time_confidence,
        },
        "lagna": {
            "longitude": chart.ascendant,
            "sign": chart.lagna_sign,
            "sign_name": SIGNS[chart.lagna_sign],
            "degree_in_sign": chart.ascendant % 30.0,
        },
        "positions": {
            body: {
                "longitude": position.longitude,
                "sign": position.sign,
                "sign_name": position.sign_name,
                "degree_in_sign": position.degree_in_sign,
                "nakshatra": position.nakshatra,
                "nakshatra_name": position.nakshatra_name,
                "pada": position.pada,
                "retrograde": position.retrograde,
                "speed": position.speed,
                "house": chart.house_of(body),
            }
            for body, position in chart.positions.items()
        },
        "vargas": {
            f"D{divisor}": _varga_payload(chart, divisor) for divisor in vargas
        },
        "conditions": {
            body: {
                "dignity": condition.dignity,
                "combust": condition.combust,
                "retrograde": condition.retrograde,
                "dig_bala": condition.has_dig_bala,
                "benefic": condition.is_benefic,
                "owns_houses": list(condition.owns_houses),
                "aspects_houses": list(condition.aspects_houses),
                "vargottama": natal.facts.is_vargottama(body),
            }
            for body, condition in natal.facts.condition.items()
        },
        "yogas": yoga_payload(natal),
        "ashtakavarga": ashtakavarga_payload(natal),
        "shadbala": shadbala_payload(natal),
        "karakas": karaka_payload(natal.chart),
        "yogakarakas": list(natal.facts.yogakarakas),
        "dasha": {
            "balance_at_birth": {"lord": balance_lord, "years": round(balance_years, 4)},
            "as_of": jd_to_iso(reference_jd),
            "current": [_period_payload(p, include_children=False) for p in current],
            "mahadashas": [
                _period_payload(period, include_children=False)
                for period in natal.dashas
            ],
        },
    }


def yoga_payload(natal: NatalChart) -> list[dict]:
    """Yogas that actually fire, plain wording first and the technical basis attached.

    Nothing is invented here: the list is exactly the rules whose conditions the chart
    satisfies, each carrying the citation and the placements that triggered it.
    """
    findings = apply_rules(rules(), natal.facts)
    return [
        {
            "id": finding.rule.id,
            "name": finding.rule.name,
            # The plain wording is what the reading views show, so it obeys the
            # vocabulary rule; the technical summary keeps the terms as written.
            "plain": plainly(" ".join(finding.rule.plain.split())),
            "summary": " ".join(finding.rule.summary.split()),
            "polarity": finding.rule.polarity,
            "domains": list(finding.rule.domains),
            "citation": finding.citation,
            "citation_located": finding.rule.citation.located,
            # Structured so the dashboard can fetch the passage itself. A citation
            # nobody can open is decoration.
            "citation_ref": {
                "work": finding.rule.citation.text,
                "chapter": finding.rule.citation.chapter,
                "verse": finding.rule.citation.verse,
                "page": finding.rule.citation.page,
            },
            "note": " ".join(finding.rule.note.split()),
            "evidence": list(finding.evidence),
        }
        for finding in findings
    ]


def shadbala_payload(natal: NatalChart) -> dict:
    """The six-fold strength of each graha.

    The day boundaries are fetched here rather than inside `shadbala`, so that module
    stays arithmetic over a chart and does not reach for an ephemeris of its own. At a
    polar latitude there are none, and the two hour-based parts are left out instead of
    guessed — which the payload says, so a reader is not comparing an incomplete total
    against a full one without knowing.
    """
    chart = natal.chart
    span = day_span(chart.jd_ut, chart.latitude, chart.longitude)
    data = shadbala_payload_of(shadbala(chart, span))
    data["hour_based_parts"] = span is not None
    return data


def ashtakavarga_payload(natal: NatalChart) -> dict:
    """Bindu counts by house, with the reading thresholds attached so the dashboard and
    the rules cannot drift apart on what counts as strong."""
    varga = natal.facts.ashtakavarga
    houses = []
    for house in range(1, 13):
        sign = natal.facts.sign_of_house(house)
        total = varga.sav(sign)
        houses.append(
            {
                "house": house,
                "sign": sign,
                "sign_name": SIGNS[sign],
                "sav": total,
                "reading": "strong" if total >= SAV_STRONG else "weak" if total <= SAV_WEAK else "average",
                "bav": {body: varga.bav(body, sign) for body in varga.bhinna},
            }
        )
    # The reductions of ch. 67-69. Kept separate from the raw counts because they are
    # a different thing: shodhya pinda is used for longevity work, not for reading a
    # house's support, and merging them would invite comparing unlike numbers.
    reduced = reduced_ashtakavarga(natal.chart)

    return {
        "houses": houses,
        "totals": {body: sum(counts) for body, counts in varga.bhinna.items()},
        "sav_total": sum(varga.sarva),
        "thresholds": {"strong": SAV_STRONG, "weak": SAV_WEAK},
        "reductions": {
            "citation": (
                "Brihat Parashara Hora Shastra, ch. 67 (trikona), ch. 68 "
                "(ekadhipatya) and ch. 69 (pinda)"
            ),
            "by_planet": {
                body: {
                    "reduced": list(values["reduced"]),
                    "reduced_total": sum(values["reduced"]),
                    "rasi_pinda": values["rasi_pinda"],
                    "graha_pinda": values["graha_pinda"],
                    "sodhya_pinda": values["sodhya_pinda"],
                }
                for body, values in reduced.items()
            },
        },
    }


def transit_payload(
    natal: NatalChart,
    *,
    at_jd: float | None = None,
    months_ahead: int = 24,
) -> dict:
    """Where the grahas are now against this chart, and what changes over the next
    stretch of time.

    Both transit doctrines are reported side by side. Where they disagree the reader is
    told, rather than being shown one verdict that hides the other.
    """
    reference_jd = now_jd() if at_jd is None else at_jd
    horizon_jd = reference_jd + months_ahead * 30.44
    chart = natal.chart
    varga = natal.facts.ashtakavarga

    standings = gochara(chart, varga, reference_jd)
    chain = chain_at(natal.dashas, reference_jd)

    windows = []
    for body in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        windows.extend(retrograde_windows(chart, body, reference_jd, horizon_jd))
    for body in ("Mercury", "Venus"):
        windows.extend(combustion_windows(chart, body, reference_jd, horizon_jd))
    windows.extend(sade_sati(chart, reference_jd, horizon_jd))
    windows.sort(key=lambda window: window.start_jd)

    return {
        "as_of": jd_to_iso(reference_jd),
        "horizon": jd_to_iso(horizon_jd),
        "gochara": {
            body: {
                "sign": standing.sign,
                "sign_name": standing.sign_name,
                "degree_in_sign": standing.degree_in_sign,
                "retrograde": standing.retrograde,
                "house_from_moon": standing.house_from_moon,
                "house_from_lagna": standing.house_from_lagna,
                "bindus": standing.bindus,
                "supported": standing.supported,
                "traditionally_good": standing.traditionally_good,
                "doctrines_agree": standing.agrees,
            }
            for body, standing in standings.items()
        },
        "contacts": [
            {
                "transiting": contact.transiting,
                "natal_point": contact.natal_point,
                "kind": contact.kind,
                "separation": round(contact.separation, 3),
                "natal_house": contact.natal_house,
            }
            for contact in contacts(chart, reference_jd)
        ],
        "windows": [
            {
                "body": window.body,
                "kind": window.kind,
                "label": window.label,
                "detail": window.detail,
                "start": jd_to_iso(window.start_jd),
                "end": jd_to_iso(window.end_jd),
                "days": round(window.days, 1),
            }
            for window in windows
        ],
        "confluence": confluence(chart, varga, chain, reference_jd),
    }


def _varga_payload(chart: Chart, divisor: int) -> dict:
    if divisor not in SHODASAVARGA:
        raise ValueError(f"D{divisor} is not one of the shodasavarga")
    varga = varga_chart(chart, divisor)
    return {
        "divisor": varga.divisor,
        "name": varga.name,
        "lagna_sign": varga.lagna_sign,
        "lagna_sign_name": SIGNS[varga.lagna_sign],
        "signs": {
            body: {
                "sign": sign,
                "sign_name": SIGNS[sign],
                "house": varga.house_of(body),
            }
            for body, sign in varga.signs.items()
        },
    }


def dasha_tree_payload(natal: NatalChart) -> list[dict]:
    """The full nested dasha tree. Separate from the main payload because it is large
    and the dashboard only needs it when the timeline is expanded."""
    return [_period_payload(period, include_children=True) for period in natal.dashas]


def life_stages_payload(
    natal: NatalChart, *, at_jd: float | None = None, years_ahead: int = 12
) -> dict:
    """The timeline that is the dashboard's main view.

    Plain wording first, the drivers behind every score attached underneath.
    """
    start = now_jd() if at_jd is None else at_jd
    end = start + years_ahead * 365.25
    stages = life_stages(natal.facts, natal.dashas, start, end)

    return {
        "as_of": jd_to_iso(start),
        "horizon": jd_to_iso(end),
        "domains": {
            name: {"houses": list(definition["houses"]), "why": definition["why"],
                   "citation": definition["citation"]}
            for name, definition in DOMAINS.items()
        },
        "stages": [
            {
                "start": jd_to_iso(stage.start_jd),
                "end": jd_to_iso(stage.end_jd),
                "years": round(stage.years, 2),
                "current": stage.start_jd <= start < stage.end_jd,
                "headline": stage.headline(),
                "mahadasha": stage.mahadasha,
                "antardasha": stage.antardasha,
                # What BPHS ch. 52-60 says of this exact pair of periods. The most
                # personal thing the library has about a stretch of time: not what a
                # graha does in general, but what it does inside this other one's years.
                "says": _antardasha_says(stage.mahadasha, stage.antardasha),
                "opened_by": list(stage.opened_by),
                "transits": list(stage.transits),
                "domains": [
                    {
                        "domain": reading.domain,
                        "score": reading.score,
                        "verdict": reading.verdict,
                        "distinguishing": stage.distinguishing(reading.domain),
                        "drivers": [
                            {"text": driver.text, "weight": driver.weight}
                            for driver in reading.drivers
                        ],
                    }
                    for reading in stage.domains
                ],
            }
            for stage in stages
        ],
    }


def _antardasha_says(mahadasha: str, antardasha: str | None) -> dict | None:
    from astro.corpus.index import antardasha_effect

    if antardasha is None:
        return None
    found = antardasha_effect(mahadasha, antardasha)
    if found is None:
        return None
    text, hit = found
    return {
        "text": text.translate(_SCANNED_QUOTES),
        "citation": hit.citation,
        "work": hit.work,
        "chapter": hit.chapter,
        "verse": hit.verses,
        "page": hit.page,
    }


# The scan renders every apostrophe as a low double quote; fixed on the way out.
_SCANNED_QUOTES = str.maketrans({"\u201f": "\u2019", "\u201e": "\u2019", "\u201b": "\u2019"})


def remedies_for(natal: NatalChart) -> dict:
    return remedies_payload(natal.facts)


def synastry_payload(first: NatalChart, second: NatalChart) -> dict:
    """Compatibility between two natives, by both systems.

    The kuta total is the popular answer and is given first because it is what people
    ask for. The seventh-house reading is what the ingested text actually prescribes,
    and it is the only part of this with a citation.
    """
    result = match(first.facts, second.facts)
    return {
        "between": [first.profile.name, second.profile.name],
        "note": (
            "The eight-factor total is the popular matching system. It is not in the "
            "ingested Brihat Parashara Hora Shastra — searching for kuta, yoni, gana, "
            "bhakoot and nadi returns nothing — so no verse is cited for it. The "
            "seventh-house reading below is what this text does prescribe."
        ),
        "total": result.total,
        "maximum": result.maximum,
        "verdict": result.verdict,
        "kutas": [
            {
                "name": kuta.name,
                "points": kuta.points,
                "maximum": kuta.maximum,
                "reason": kuta.reason,
                "precision": kuta.precision,
                "caveat": kuta.caveat,
            }
            for kuta in result.kutas
        ],
        "doshas": [
            {
                "name": dosha.name,
                "present": dosha.present,
                "reason": dosha.reason,
                "cancelled_by": dosha.cancelled_by,
            }
            for dosha in result.doshas
        ],
        "seventh_house": {
            first.profile.name: seventh_house_reading(first.facts),
            second.profile.name: seventh_house_reading(second.facts),
        },
    }


def _limb(limb) -> dict:
    return {
        "name": limb.name,
        "index": limb.index,
        "ends": jd_to_iso(limb.ends_jd) if limb.ends_jd else None,
        "note": limb.note,
    }


def panchanga_payload(natal: NatalChart, *, at_jd: float | None = None) -> dict:
    """The five limbs of the day, both at birth and now.

    Computed locally from the Sun and Moon rather than fetched: it is arithmetic on two
    longitudes, and sending birth data to a service to get it back would be a bad trade.
    """
    latitude, longitude = natal.profile.latitude, natal.profile.longitude
    birth = compute_panchanga(
        natal.moment.jd_ut, latitude, longitude, ayanamsa=natal.chart.ayanamsa
    )
    reference = now_jd() if at_jd is None else at_jd
    today = compute_panchanga(reference, latitude, longitude, ayanamsa=natal.chart.ayanamsa)

    def shape(value) -> dict:
        return {
            "at": jd_to_iso(value.jd),
            "tithi": _limb(value.tithi),
            "paksha": value.paksha,
            "tithi_group": value.tithi_group,
            "vara": _limb(value.vara),
            "nakshatra": _limb(value.nakshatra),
            "yoga": _limb(value.yoga),
            "karana": _limb(value.karana),
            "flags": list(value.flags),
        }

    return {"birth": shape(birth), "today": shape(today)}
