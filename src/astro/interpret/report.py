"""The complete written report for one native.

Assembled from computed facts and fired rules, in a fixed section order so two family
members' reports can be read side by side. No prose is generated: every sentence is
built from values the rest of the package produced, which is why this module has no
model dependency and its output is identical between runs.

Markdown is the output format. Turning it into a PDF is one shell command with pandoc
or the make-pdf skill, and hard-wiring a PDF library here would add a dependency for
something the user may want styled their own way.
"""

from __future__ import annotations

from astro.core.ephemeris import SIGNS
from astro.interpret.life_stages import DOMAINS, life_stages, ordinal, readable
from astro.interpret.remedies import DISCLAIMER, remedies
from astro.service import NatalChart, jd_to_iso, now_jd, rules
from astro.rules.engine import apply_rules


def _heading(level: int, text: str) -> str:
    return f"{'#' * level} {text}\n"


def _birth_section(natal: NatalChart) -> str:
    moment = natal.moment
    profile = natal.profile
    lines = [
        _heading(2, "Birth data and settings"),
        "",
        f"- **Name**: {profile.name}" + (f" ({profile.relation})" if profile.relation else ""),
        f"- **Born**: {moment.local_datetime:%d %B %Y at %H:%M} "
        f"in {profile.place or 'an unrecorded place'}",
        f"- **Universal time**: {moment.utc_datetime:%Y-%m-%d %H:%M} "
        f"({moment.timezone_name}, {moment.offset_label})",
        f"- **Birth time confidence**: {profile.time_confidence.replace('_', ' ')}",
        f"- **Ayanamsa**: {natal.chart.ayanamsa} ({natal.chart.ayanamsa_value:.4f}°)",
        f"- **House system**: {natal.chart.house_system.replace('_', ' ')}; "
        f"**nodes**: {natal.chart.node_type}",
        "",
    ]
    if moment.warnings:
        lines.append("**Notes on the birth time**\n")
        lines += [f"- {warning}" for warning in moment.warnings]
        lines.append("")
    if profile.time_confidence not in ("exact", "to_the_minute"):
        lines.append(
            "> The rising sign changes roughly every two hours, so house placements "
            "below should be treated as provisional until the birth time is confirmed.\n"
        )
    return "\n".join(lines)


def _overview_section(natal: NatalChart) -> str:
    chart = natal.chart
    moon = chart.positions["Moon"]
    return "\n".join(
        [
            _heading(2, "The chart in one paragraph"),
            "",
            f"The rising sign is **{SIGNS[chart.lagna_sign]}**, so the chart is read "
            f"from there. The Moon is in **{moon.sign_name}**, in the nakshatra "
            f"**{moon.nakshatra_name}** (pada {moon.pada}), which sets the whole dasha "
            f"timeline. The lagna lord is **{natal.facts.lagna_lord}**, in the "
            f"{ordinal(natal.facts.condition[natal.facts.lagna_lord].house)} "
            f"({readable(natal.facts.dignity(natal.facts.lagna_lord))}).",
            "",
        ]
    )


def _positions_section(natal: NatalChart) -> str:
    lines = [
        _heading(2, "Planetary positions"),
        "",
        "| Planet | Sign | Degree | House | Nakshatra | Dignity | Notes |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for body, position in natal.chart.positions.items():
        condition = natal.facts.condition[body]
        notes = []
        if condition.retrograde and body not in ("Rahu", "Ketu"):
            notes.append("retrograde")
        if condition.combust:
            notes.append("combust")
        if condition.has_dig_bala:
            notes.append("directional strength")
        if natal.facts.is_vargottama(body):
            notes.append("vargottama")
        lines.append(
            f"| {body} | {position.sign_name} | {position.degree_in_sign:.2f}° | "
            f"{condition.house} | {position.nakshatra_name} | "
            f"{readable(condition.dignity)} | "
            f"{', '.join(notes) or '—'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _houses_section(natal: NatalChart) -> str:
    lines = [_heading(2, "House by house"), ""]
    for house in range(1, 13):
        facts = natal.facts
        occupants = facts.occupants(house)
        lord = facts.lord_of(house)
        domains = [
            domain
            for domain, definition in DOMAINS.items()
            if house in definition["houses"]
        ]
        lines.append(
            f"**The {ordinal(house)} house — {SIGNS[facts.sign_of_house(house)]}**"
            + (f" _({', '.join(domains)})_" if domains else "")
        )
        lines.append(
            f"Ruled by {lord}, which sits in the {ordinal(facts.lord_placed_in(house))} "
            f"({readable(facts.dignity(lord))}). "
            + (
                f"Occupied by {', '.join(occupants)}. "
                if occupants
                else "No planet occupies it. "
            )
            + f"Ashtakavarga support: {facts.sav_of_house(house)} points."
        )
        lines.append("")
    return "\n".join(lines)


def _yogas_section(natal: NatalChart) -> str:
    findings = apply_rules(rules(), natal.facts)
    lines = [_heading(2, "Combinations present"), ""]
    if not findings:
        lines += [
            "None of the combinations currently encoded are present. That is a "
            "statement about the rules checked, not a verdict on the chart.",
            "",
        ]
        return "\n".join(lines)

    for polarity, title in (("benefic", "Supportive"), ("malefic", "Challenging")):
        group = [f for f in findings if f.rule.polarity == polarity]
        if not group:
            continue
        lines += [_heading(3, title), ""]
        for finding in group:
            lines.append(f"**{finding.rule.name}.** {' '.join(finding.rule.plain.split())}")
            lines.append("")
            lines.append(f"- Condition: {' '.join(finding.rule.summary.split())}")
            for line in finding.evidence:
                lines.append(f"- {line}")
            lines.append(f"- Source: {finding.citation}")
            if finding.rule.note:
                lines.append(f"- Note: {' '.join(finding.rule.note.split())}")
            lines.append("")
    return "\n".join(lines)


def _ashtakavarga_section(natal: NatalChart) -> str:
    varga = natal.facts.ashtakavarga
    lines = [
        _heading(2, "House support (ashtakavarga)"),
        "",
        "A points system scoring each house out of the whole chart. The twelve always "
        "total 337.",
        "",
        "| House | Sign | Points | Reading |",
        "| ---: | --- | ---: | --- |",
    ]
    for house in range(1, 13):
        sign = natal.facts.sign_of_house(house)
        total = varga.sav(sign)
        reading = "strong" if total >= 30 else "weak" if total <= 25 else "average"
        lines.append(f"| {house} | {SIGNS[sign]} | {total} | {reading} |")
    lines.append("")
    return "\n".join(lines)


def _stages_section(natal: NatalChart, from_jd: float, to_jd: float) -> str:
    stages = life_stages(natal.facts, natal.dashas, from_jd, to_jd)
    lines = [
        _heading(2, "The years ahead"),
        "",
        f"Chapters between {jd_to_iso(from_jd)[:10]} and {jd_to_iso(to_jd)[:10]}. Each "
        "begins where a planetary period changes or a slow planet changes sign.",
        "",
    ]
    for stage in stages:
        lines.append(
            _heading(
                3,
                f"{jd_to_iso(stage.start_jd)[:10]} to {jd_to_iso(stage.end_jd)[:10]} "
                f"— {stage.mahadasha}"
                + (f"/{stage.antardasha}" if stage.antardasha else ""),
            )
        )
        lines.append("")
        lines.append(stage.headline())
        lines.append("")
        lines.append(f"_Opens with: {'; '.join(stage.opened_by)}._")
        lines.append("")
        for reading in sorted(stage.domains, key=lambda r: -abs(r.score)):
            if not reading.drivers:
                continue
            lines.append(
                f"- **{reading.domain}** — {reading.verdict} "
                f"({reading.score:+d})" .replace("(+0)", "(neutral)") + ": "
                + "; ".join(driver.text for driver in reading.drivers)
            )
        lines.append("")
    return "\n".join(lines)


def _remedies_section(natal: NatalChart) -> str:
    found = remedies(natal.facts)
    lines = [_heading(2, "Remedies"), ""]
    if not found:
        lines += ["Nothing indicated by the rules currently encoded.", ""]
        return "\n".join(lines)

    by_source: dict[str, list] = {}
    for finding in found:
        by_source.setdefault(finding.rule.citation.text, []).append(finding)

    lines += [f"_{DISCLAIMER}_", ""]
    for source, group in by_source.items():
        lines += [_heading(3, f"From {source}"), ""]
        for finding in group:
            lines.append(f"**{finding.rule.name}.** {' '.join(finding.rule.plain.split())}")
            lines.append("")
            lines.append(f"- Because: {' '.join(finding.rule.summary.split())}")
            lines.append(f"- Source: {finding.citation}")
            if finding.rule.note:
                lines.append(f"- Note: {' '.join(finding.rule.note.split())}")
            lines.append("")
    return "\n".join(lines)


def build_report(
    natal: NatalChart,
    *,
    from_jd: float | None = None,
    years_ahead: int = 10,
) -> str:
    """The whole report as markdown.

    `from_jd` defaults to now and exists so tests are not time-dependent.
    """
    start = now_jd() if from_jd is None else from_jd
    end = start + years_ahead * 365.25

    sections = [
        _heading(1, f"Vedic astrology reading — {natal.profile.name}"),
        "",
        _birth_section(natal),
        _overview_section(natal),
        _positions_section(natal),
        _houses_section(natal),
        _yogas_section(natal),
        _ashtakavarga_section(natal),
        _stages_section(natal, start, end),
        _remedies_section(natal),
        _heading(2, "How to read this"),
        "",
        "Every claim above is either a computed position or a rule from a named text. "
        "Where a rule's chapter and verse were found in an ingested source they are "
        "given; where they were not, the report says so rather than implying a source "
        "was checked. Scores are sums of the drivers listed beside them.",
        "",
    ]
    return "\n".join(sections)
