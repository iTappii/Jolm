"""Pure parser for the common, simple subset of OSM `opening_hours`.

Supported: "24/7"; "Mo-Fr 09:00-18:00; Sa,Su 10:00-16:00"; bare "09:00-18:00" (all days);
several intervals "09:00-13:00,14:00-18:00"; "Su off"; intervals past midnight "18:00-02:00".
Anything else (PH, sunrise, months, week numbers, "+", comments...) -> None (caller counts it).

Result: list of (weekday, opens, closes); weekday 0 = Monday. 24:00 is stored as 23:59.
"""

from __future__ import annotations

import re
from datetime import time
from typing import Dict, List, Optional, Tuple

DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
_TIME = r"([01]?\d|2[0-4]):([0-5]\d)"
_INTERVAL = re.compile(rf"^{_TIME}\s*-\s*{_TIME}$")
_DAY_TOKEN = re.compile(r"^(Mo|Tu|We|Th|Fr|Sa|Su)(?:\s*-\s*(Mo|Tu|We|Th|Fr|Sa|Su))?$")

Interval = Tuple[time, time]
Hours = List[Tuple[int, time, time]]


def _to_time(hour: str, minute: str) -> Optional[time]:
    h, m = int(hour), int(minute)
    if h == 24:
        return time(23, 59) if m == 0 else None
    return time(h, m)


def _parse_days(spec: str) -> Optional[List[int]]:
    days: List[int] = []
    for token in spec.split(","):
        m = _DAY_TOKEN.match(token.strip())
        if not m:
            return None
        start = DAYS.index(m.group(1))
        end = DAYS.index(m.group(2)) if m.group(2) else start
        d = start
        days.append(d)
        while d != end:  # supports wrap-around such as Fr-Mo
            d = (d + 1) % 7
            days.append(d)
    return days


def _parse_intervals(spec: str) -> Optional[List[Interval]]:
    out: List[Interval] = []
    for part in spec.split(","):
        m = _INTERVAL.match(part.strip())
        if not m:
            return None
        opens, closes = _to_time(m.group(1), m.group(2)), _to_time(m.group(3), m.group(4))
        if opens is None or closes is None:
            return None
        out.append((opens, closes))
    return out


def parse_opening_hours(value: Optional[str]) -> Optional[Hours]:
    """Parse the simple subset; None when empty or not understood."""
    if not value or not value.strip():
        return None
    text = value.strip()
    if text == "24/7":
        return [(d, time(0, 0), time(23, 59)) for d in range(7)]
    by_day: Dict[int, List[Interval]] = {}
    for rule in text.split(";"):
        rule = rule.strip()
        if not rule:
            continue
        m = re.match(
            r"^((?:(?:Mo|Tu|We|Th|Fr|Sa|Su)(?:\s*-\s*(?:Mo|Tu|We|Th|Fr|Sa|Su))?)"
            r"(?:\s*,\s*(?:Mo|Tu|We|Th|Fr|Sa|Su)(?:\s*-\s*(?:Mo|Tu|We|Th|Fr|Sa|Su))?)*)"
            r"\s+(.+)$",
            rule,
        )
        if m:
            days = _parse_days(m.group(1))
            rest = m.group(2).strip()
        elif re.match(r"^\d", rule):
            days, rest = list(range(7)), rule
        else:
            return None
        if days is None:
            return None
        if rest in ("off", "closed"):
            intervals: List[Interval] = []
        else:
            parsed = _parse_intervals(rest)
            if parsed is None:
                return None
            intervals = parsed
        for d in days:
            by_day[d] = list(intervals)  # a later rule overrides earlier ones for that day
    result: Hours = []
    for d in sorted(by_day):
        for opens, closes in by_day[d]:
            result.append((d, opens, closes))
    return result or None
