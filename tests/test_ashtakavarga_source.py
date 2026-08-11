"""Check the ashtakavarga tables against the primary text.

BPHS states each graha's ashtakavarga house by house — "Lagn, Sukr and Candr in the
1st; ..." — while the code stores it contributor by contributor. This transcribes the
verses as printed in `corpus_md/`, transposes them, and diffs.

The point is not that they must match everywhere. Editions genuinely differ, and this
one has an arithmetic slip in Jupiter's table. The point is that every difference is
declared in `KNOWN_VARIANTS`: a new one appearing means either the code changed or the
transcription is wrong, and both deserve to fail the build.
"""

from __future__ import annotations

import pytest

from astro.core.ashtakavarga import (
    BENEFIC_PLACES,
    CONTRIBUTORS,
    EXPECTED_TOTALS,
    KNOWN_VARIANTS,
    SUBJECTS,
)

ALL = list(CONTRIBUTORS)


def _all_but(*excluded: str) -> list[str]:
    return [body for body in ALL if body not in excluded]


# Transcribed from Brihat Parashara Hora Shastra, ch. 66, v. 43-60, as rendered in
# corpus_md/brihat_parashara_hora_shastra_english_v.jsonl. Sanskrit names mapped:
# Surya=Sun, Candr=Moon, Mangal=Mars, Budh=Mercury, Guru=Jupiter, Sukr=Venus,
# Sani=Saturn, Lagn=Lagna.
TEXT_BY_HOUSE: dict[str, dict[int, list[str]]] = {
    "Sun": {  # v43-45
        1: ["Saturn", "Mars", "Sun"],
        2: ["Saturn", "Mars", "Sun"],
        3: ["Mercury", "Moon", "Lagna"],
        4: ["Lagna", "Sun", "Saturn", "Mars"],
        5: ["Jupiter", "Mercury"],
        6: ["Lagna", "Venus", "Mercury", "Jupiter", "Moon"],
        7: ["Sun", "Mars", "Saturn", "Venus"],
        8: ["Saturn", "Mars", "Sun"],
        9: ["Sun", "Mars", "Saturn", "Mercury", "Jupiter"],
        10: ["Lagna", "Sun", "Saturn", "Mars", "Mercury", "Moon"],
        11: ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Saturn", "Lagna"],
        12: ["Lagna", "Venus", "Mercury"],
    },
    "Moon": {  # v46-48
        1: ["Mercury", "Moon", "Jupiter"],
        2: ["Jupiter", "Mars"],
        3: ["Mercury", "Sun", "Moon", "Mars", "Saturn", "Venus", "Lagna"],
        4: ["Jupiter", "Venus", "Mercury"],
        5: ["Mars", "Mercury", "Venus", "Saturn"],
        6: ["Sun", "Moon", "Mars", "Saturn", "Lagna"],
        7: ["Sun", "Moon", "Jupiter", "Mercury", "Venus"],
        8: ["Sun", "Mercury", "Jupiter"],
        9: ["Venus", "Moon"],
        10: ["Sun", "Mercury", "Jupiter", "Venus", "Moon", "Lagna", "Mars"],
        11: ALL,
        12: [],
    },
    "Mars": {  # v49-50
        1: ["Lagna", "Saturn", "Mars"],
        2: ["Mars"],
        3: ["Lagna", "Mercury", "Moon", "Sun"],
        4: ["Saturn", "Mars"],
        5: ["Mercury", "Sun"],
        6: ["Mercury", "Moon", "Jupiter", "Sun", "Lagna", "Venus"],
        7: ["Saturn", "Mars"],
        8: ["Saturn", "Mars", "Venus"],
        9: ["Saturn"],
        10: ["Mars", "Sun", "Jupiter", "Saturn", "Lagna"],
        11: ALL,
        12: ["Jupiter", "Venus"],
    },
    "Mercury": {  # v51-52
        1: ["Lagna", "Saturn", "Mars", "Venus", "Mercury"],
        2: ["Lagna", "Mars", "Moon", "Venus", "Saturn"],
        3: ["Venus", "Mercury"],
        4: ["Lagna", "Moon", "Saturn", "Venus", "Mars"],
        5: ["Mercury", "Saturn", "Venus"],
        6: ["Jupiter", "Mercury", "Sun", "Moon", "Lagna"],
        7: ["Mars", "Saturn"],
        8: ["Mars", "Saturn", "Lagna", "Moon", "Venus", "Jupiter"],
        9: ["Saturn", "Mars", "Sun", "Mercury", "Venus"],
        10: ["Lagna", "Saturn", "Mars", "Mercury", "Moon"],
        11: ALL,
        12: ["Jupiter", "Mercury", "Sun"],
    },
    "Jupiter": {  # v53-55
        1: ["Lagna", "Mars", "Sun", "Mercury"],
        2: ["Jupiter", "Lagna", "Mars", "Sun", "Mercury", "Moon", "Venus"],
        3: ["Saturn", "Jupiter", "Sun"],
        4: ["Lagna", "Mars", "Sun", "Mercury"],
        5: ["Venus", "Moon", "Lagna", "Mercury", "Saturn"],
        6: ["Venus", "Lagna", "Mercury", "Saturn"],
        7: ["Lagna", "Mars", "Jupiter", "Sun", "Moon"],
        8: ["Jupiter", "Sun", "Mars"],
        9: ["Venus", "Sun", "Lagna", "Moon", "Mercury"],
        10: ["Jupiter", "Mercury", "Mars", "Sun", "Venus", "Lagna"],
        11: _all_but("Saturn"),
        12: ["Saturn"],
    },
    "Venus": {  # v56-58
        1: ["Lagna", "Venus", "Moon"],
        2: ["Lagna", "Venus", "Moon"],
        3: ["Lagna", "Venus", "Moon", "Mercury", "Saturn", "Mars"],
        4: ["Lagna", "Venus", "Moon", "Saturn", "Mars"],
        5: ["Lagna", "Mercury", "Moon", "Jupiter", "Saturn", "Venus"],
        6: ["Mercury", "Mars"],
        7: [],
        8: ["Venus", "Sun", "Moon", "Jupiter", "Lagna", "Saturn"],
        9: _all_but("Sun"),
        10: ["Venus", "Jupiter", "Saturn"],
        11: ALL,
        12: ["Mars", "Moon", "Sun"],
    },
    "Saturn": {  # v59-60
        1: ["Sun", "Lagna"],
        2: ["Sun"],
        3: ["Lagna", "Moon", "Mars", "Saturn"],
        4: ["Lagna", "Sun"],
        5: ["Jupiter", "Saturn", "Mars"],
        6: _all_but("Sun"),
        7: ["Sun"],
        8: ["Sun", "Mercury"],
        9: ["Mercury"],
        10: ["Sun", "Mars", "Lagna", "Mercury"],
        11: ALL,
        12: ["Mars", "Mercury", "Jupiter", "Venus"],
    },
}


def transposed(subject: str) -> dict[str, tuple[int, ...]]:
    """The text's house-by-house lists, turned into contributor-by-contributor rows."""
    by_house = TEXT_BY_HOUSE[subject]
    return {
        contributor: tuple(
            house for house in range(1, 13) if contributor in by_house.get(house, [])
        )
        for contributor in ALL
    }


@pytest.mark.parametrize("subject", SUBJECTS)
def test_differences_from_the_text_are_all_declared(subject):
    declared = KNOWN_VARIANTS["bphs_english_edition"]
    from_text = transposed(subject)

    for contributor in ALL:
        if from_text[contributor] == BENEFIC_PLACES[subject][contributor]:
            continue
        key = (subject, contributor)
        assert key in declared, (
            f"undeclared difference for {subject} from {contributor}: "
            f"text={from_text[contributor]} code={BENEFIC_PLACES[subject][contributor]}"
        )
        expected_code, expected_text = declared[key]
        assert BENEFIC_PLACES[subject][contributor] == expected_code
        assert from_text[contributor] == expected_text


@pytest.mark.parametrize("subject", SUBJECTS)
def test_the_text_reproduces_the_canonical_totals_except_for_jupiter(subject):
    """Six of the seven tables in this edition add up exactly.

    Jupiter's comes to 54 against a required 56, because the edition omits Jupiter from
    the 1st and 4th of its own varga. That is an error in the edition rather than a
    reading to follow, and it is the reason the code does not simply take the text
    wholesale.
    """
    total = sum(len(places) for places in transposed(subject).values())
    if subject == "Jupiter":
        assert total == 54
        assert EXPECTED_TOTALS[subject] == 56
    else:
        assert total == EXPECTED_TOTALS[subject]


def test_the_disputed_venus_cell_follows_the_text():
    """Venus from Mars: the text gives 3, 4, 6, 9, 11, 12 and VedAstro gives 3, 5, 6.

    Recorded explicitly because the VedAstro reading looks like a correction when found
    in isolation, and changing it here silently moves a bindu in every chart.
    """
    assert transposed("Venus")["Mars"] == (3, 4, 6, 9, 11, 12)
    assert BENEFIC_PLACES["Venus"]["Mars"] == (3, 4, 6, 9, 11, 12)
    ours, theirs = KNOWN_VARIANTS["vedastro"][("Venus", "Mars")]
    assert ours == (3, 4, 6, 9, 11, 12)
    assert theirs == (3, 5, 6, 9, 11, 12)
