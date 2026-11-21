"""Texts of the assistant's live-plan messages and pushes (RU / EN). Templates, not the LLM:
deterministic, free, testable; the sender is the assistant role of the trip's chat."""

from datetime import date
from typing import Dict, List, Optional

from app.live.rules import Problem

_MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]  # fmt: skip
_MONTHS_EN = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]  # fmt: skip

PROBLEM = {
    "thunderstorm": {"ru": "гроза", "en": "a thunderstorm"},
    "rain": {"ru": "дождь", "en": "rain"},
    "wind": {"ru": "сильный ветер", "en": "strong wind"},
    "heat": {"ru": "сильная жара", "en": "heat"},
    "cold": {"ru": "мороз", "en": "freezing temperatures"},
}


def day_text(day: date, locale: str) -> str:
    if locale == "ru":
        return "%d %s" % (day.day, _MONTHS_RU[day.month - 1])
    return "%s %d" % (_MONTHS_EN[day.month - 1], day.day)


def _hour(problem: Problem) -> str:
    return "%02d:00" % problem.hours[0]


def proposal_texts(
    locale: str,
    kind: str,
    problem: Problem,
    day: date,
    place: str,
    to_day: Optional[date] = None,
    target: Optional[str] = None,
) -> Dict[str, str]:
    """{"title", "body", "message"}: push title / push body / the chat message."""
    what = PROBLEM[problem.kind][locale]
    if locale == "ru":
        head = "Прогноз изменился: %s около %s ожидается %s" % (
            day_text(day, "ru"),
            _hour(problem),
            what,
        )
        if kind == "move_day":
            offer = "Предлагаю перенести «%s» на %s." % (place, day_text(to_day, "ru"))
        else:
            offer = "Предлагаю заменить «%s» на «%s» (в помещении)." % (place, target)
        return {
            "title": "Погода меняет план",
            "body": "%s: «%s» пострадает. %s" % (what.capitalize(), place, offer),
            "message": "%s, а «%s» под открытым небом. %s Принять изменение?"
            % (head, place, offer),
        }
    head = "The forecast changed: %s around %s, %s" % (day_text(day, "en"), _hour(problem), what)
    if kind == "move_day":
        offer = "I suggest moving %s to %s." % (place, day_text(to_day, "en"))
    else:
        offer = "I suggest swapping %s for %s (indoors)." % (place, target)
    return {
        "title": "Weather changes your plan",
        "body": "%s will affect %s. %s" % (what.capitalize(), place, offer),
        "message": "%s, and %s is outdoors. %s Apply the change?" % (head, place, offer),
    }


def mountain_texts(locale: str, rows: List[dict]) -> Dict[str, str]:
    """`rows`: {place, start, tmin, tmax, rain (0..1 or None), wind, problem (or None)}."""
    lines: List[str] = []
    warn = any(r["problem"] for r in rows)
    for r in rows:
        temp = "%+d...%+d°C" % (round(r["tmin"]), round(r["tmax"])) if r["tmin"] is not None else ""
        wind = " %d" % round(r["wind"]) if r["wind"] is not None else ""
        if locale == "ru":
            line = "%s (выход в %s): %s" % (r["place"], r["start"], temp)
            if wind:
                line += ", ветер до%s км/ч" % wind
            if r["rain"] is not None:
                line += ", вероятность осадков до %d%%" % round(r["rain"] * 100)
            if r["problem"]:
                line += ". Осторожно: %s" % PROBLEM[r["problem"].kind]["ru"]
        else:
            line = "%s (start %s): %s" % (r["place"], r["start"], temp)
            if wind:
                line += ", wind up to%s km/h" % wind
            if r["rain"] is not None:
                line += ", precipitation chance up to %d%%" % round(r["rain"] * 100)
            if r["problem"]:
                line += ". Careful: %s" % PROBLEM[r["problem"].kind]["en"]
        lines.append(line)
    if locale == "ru":
        head = (
            "Доброе утро! Сегодня в плане горы. Погода неважная, подумайте, идти ли:"
            if warn
            else "Доброе утро! Сегодня в плане горы. Погода подходящая, хорошего похода:"
        )
        title = "Горы сегодня: проверьте погоду"
    else:
        head = (
            "Good morning! Mountains are on today's plan. The weather is poor, think twice:"
            if warn
            else "Good morning! Mountains are on today's plan. The weather looks fine, enjoy:"
        )
        title = "Mountains today: check the weather"
    body = lines[0] if len(lines) == 1 else "; ".join(lines)
    return {"title": title, "body": body[:200], "message": head + "\n" + "\n".join(lines)}
