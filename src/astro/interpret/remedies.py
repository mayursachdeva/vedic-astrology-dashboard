"""Remedies.

The same engine as the yogas, pointed at a different rule directory. That is the whole
implementation: a remedy is a condition plus a source, and if no condition fires the
answer is that nothing is indicated.

The one thing worth stating plainly: this is not medical, financial or legal advice,
and the module says so in the payload rather than leaving it implied.
"""

from __future__ import annotations

from pathlib import Path

from astro.core.facts import ChartFacts
from astro.interpret.glossary import plainly
from astro.rules.engine import Finding, Rule, apply_rules, load_rules

REMEDIES_DIR = Path(__file__).resolve().parent.parent / "rules" / "remedies"

DISCLAIMER = (
    "Traditional observances recorded in the classical literature. They are not "
    "medical, financial or legal advice."
)

_RULES: list[Rule] | None = None


def remedy_rules() -> list[Rule]:
    global _RULES
    if _RULES is None:
        _RULES = load_rules(REMEDIES_DIR)
    return _RULES


def remedies(facts: ChartFacts) -> list[Finding]:
    """Only the remedies whose conditions the chart actually meets."""
    return apply_rules(remedy_rules(), facts)


def remedies_payload(facts: ChartFacts) -> dict:
    """Grouped by source, not merged into one confident list.

    Traditions disagree, particularly about gemstones, and flattening them would present
    a consensus that does not exist.
    """
    found = remedies(facts)

    by_source: dict[str, list[dict]] = {}
    for finding in found:
        entry = {
            "id": finding.rule.id,
            "name": finding.rule.name,
            "plain": plainly(" ".join(finding.rule.plain.split())),
            "summary": " ".join(finding.rule.summary.split()),
            "domains": list(finding.rule.domains),
            "citation": finding.citation,
            "citation_located": finding.rule.citation.located,
            "citation_ref": {
                "work": finding.rule.citation.text,
                "chapter": finding.rule.citation.chapter,
                "verse": finding.rule.citation.verse,
                "page": finding.rule.citation.page,
            },
            "note": " ".join(finding.rule.note.split()),
            "evidence": list(finding.evidence),
        }
        by_source.setdefault(finding.rule.citation.text, []).append(entry)

    return {
        "count": len(found),
        "by_source": by_source,
        "disclaimer": DISCLAIMER,
        "nothing_indicated": not found,
    }
