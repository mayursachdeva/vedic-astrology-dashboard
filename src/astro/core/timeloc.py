"""Birth time and place -> Julian Day (UT).

This is where charts most often go quietly wrong. A birth certificate records a wall
clock reading, and turning that into universal time needs the right zone, the right
historical offset, and a decision about wartime DST and pre-standardisation local mean
time. An error of four minutes can move the lagna into the previous sign.

The approach: let the IANA database do the work (it already knows India kept +5:53:20
until 1906 and ran +6:30 during the 1942-45 war), and make every remaining judgement
call explicit and recorded on the result rather than buried in a default.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder

from astro.core.ephemeris import julian_day

_finder = TimezoneFinder()

# Offsets that are not a whole number of minutes, or that carry seconds, indicate the
# IANA entry has fallen back to a city's local mean time rather than a legislated zone.
_LMT_MARKER_SECONDS = 60


@dataclass(frozen=True)
class BirthMoment:
    """A birth time resolved to UT, with the reasoning kept attached.

    `local_datetime` is what the certificate says. `basis` records how it was converted,
    and `warnings` carries anything a careful astrologer would want to know before
    trusting the lagna.
    """

    local_datetime: datetime  # naive; the wall clock at the birth place
    latitude: float
    longitude: float
    timezone_name: str
    utc_datetime: datetime
    jd_ut: float
    offset_hours: float
    basis: str  # "iana" or "true_lmt"
    warnings: tuple[str, ...]

    @property
    def offset_label(self) -> str:
        sign = "+" if self.offset_hours >= 0 else "-"
        total_seconds = round(abs(self.offset_hours) * 3600)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        tail = f":{seconds:02d}" if seconds else ""
        return f"UTC{sign}{hours:02d}:{minutes:02d}{tail}"


def find_timezone(latitude: float, longitude: float) -> str:
    """IANA zone name for a coordinate. Raises if the point has no zone (mid-ocean)."""
    name = _finder.timezone_at(lat=latitude, lng=longitude)
    if name is None:
        raise ValueError(
            f"no IANA timezone at lat={latitude}, lon={longitude}; "
            "pass timezone_name explicitly"
        )
    return name


def resolve(
    local_datetime: datetime,
    latitude: float,
    longitude: float,
    *,
    timezone_name: str | None = None,
    use_true_lmt: bool = False,
) -> BirthMoment:
    """Resolve a wall-clock birth time to UT.

    `use_true_lmt` computes local mean time from the birth longitude itself instead of
    using the IANA zone. This matters for births before standard time reached the
    region: IANA anchors a country's pre-standard offset to one reference city, so a
    birth far east or west of it can be off by tens of minutes. Prefer it only when the
    birth predates standardisation and the longitude is known accurately.
    """
    if local_datetime.tzinfo is not None:
        raise ValueError("local_datetime must be naive — it is a wall clock reading")

    warnings: list[str] = []

    if use_true_lmt:
        offset_hours = longitude / 15.0
        utc_datetime = local_datetime - timedelta(hours=offset_hours)
        resolved_zone = timezone_name or "true LMT"
        basis = "true_lmt"
        warnings.append(
            f"Local mean time from longitude {longitude:.4f}E, not a legislated zone."
        )
    else:
        resolved_zone = timezone_name or find_timezone(latitude, longitude)
        zone = ZoneInfo(resolved_zone)
        basis = "iana"

        aware = local_datetime.replace(tzinfo=zone)
        offset = aware.utcoffset()
        assert offset is not None
        offset_hours = offset.total_seconds() / 3600.0
        utc_datetime = aware.astimezone(timezone.utc).replace(tzinfo=None)

        warnings.extend(_transition_warnings(local_datetime, zone, offset))

    jd = julian_day(
        utc_datetime.year,
        utc_datetime.month,
        utc_datetime.day,
        utc_datetime.hour
        + utc_datetime.minute / 60.0
        + (utc_datetime.second + utc_datetime.microsecond / 1e6) / 3600.0,
    )

    return BirthMoment(
        local_datetime=local_datetime,
        latitude=latitude,
        longitude=longitude,
        timezone_name=resolved_zone,
        utc_datetime=utc_datetime,
        jd_ut=jd,
        offset_hours=offset_hours,
        basis=basis,
        warnings=tuple(warnings),
    )


def _transition_warnings(
    local_datetime: datetime, zone: ZoneInfo, offset: timedelta
) -> list[str]:
    """Flag the three cases where a wall clock reading is not a single instant."""
    warnings: list[str] = []

    if offset.total_seconds() % _LMT_MARKER_SECONDS:
        warnings.append(
            f"Offset {offset} carries seconds, so this date predates standard time in "
            "the zone and IANA is using a reference city's local mean time. If the "
            "birth place is far from that city, consider use_true_lmt=True."
        )

    dst = local_datetime.replace(tzinfo=zone).dst()
    if dst and dst.total_seconds():
        warnings.append(f"Daylight saving was in force ({dst} ahead of standard time).")

    # An ambiguous reading (clocks went back) resolves differently under fold=0/1; a
    # nonexistent one (clocks went forward) never occurred at all.
    earlier = local_datetime.replace(tzinfo=zone, fold=0).utcoffset()
    later = local_datetime.replace(tzinfo=zone, fold=1).utcoffset()
    if earlier != later:
        warnings.append(
            f"Ambiguous wall clock time: it occurred twice (offsets {earlier} and "
            f"{later}). Using the first. Confirm which side of the transition applies."
        )

    roundtrip = (
        local_datetime.replace(tzinfo=zone)
        .astimezone(timezone.utc)
        .astimezone(zone)
        .replace(tzinfo=None)
    )
    if roundtrip != local_datetime:
        warnings.append(
            f"This wall clock time never existed in {zone.key} — clocks jumped over it. "
            f"It has been read as {roundtrip}. Check the recorded time."
        )

    return warnings
