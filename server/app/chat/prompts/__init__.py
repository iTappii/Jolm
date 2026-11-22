"""Versioned system prompts: `<name>.<locale>.v<N>.md` files next to this module.

`load_prompt(name, locale)` returns the highest version for the locale (unknown locale -> en).
HTML comments in the files are notes for developers and are stripped; `{{today}}` is filled in
by `render`, and so are `{{region}}` (the region name in the prompt language) and `{{currency}}`
(its currency code). To change a prompt, add a new `vN+1` file instead of editing a released one, so
stored chats can say which prompt version produced an answer.
"""

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from app.regions import Region, default_region

DIR = Path(__file__).resolve().parent
LOCALES = ("ru", "en")
DEFAULT_LOCALE = "en"
TRIP_BRIEF = "trip_brief"  # registered user: collects the trip brief (Ш-31)
GUEST = "guest"  # guest: simple assistant without memory (Ш-30)

_COMMENT = re.compile(r"<!--.*?-->\s*", re.DOTALL)


@dataclass(frozen=True)
class Prompt:
    name: str
    locale: str
    version: int
    text: str

    @property
    def id(self) -> str:
        """Stable id to store next to an answer, e.g. `trip_brief.ru.v1`."""
        return f"{self.name}.{self.locale}.v{self.version}"

    def render(self, today: Optional[date] = None, region: Optional[Region] = None) -> str:
        region = region or default_region()  # Ш-57: the city and the currency come from the region
        return (
            self.text.replace("{{today}}", (today or date.today()).isoformat())
            .replace("{{region}}", region.name(self.locale))
            .replace("{{currency}}", region.currency)
        )


def versions(name: str, locale: str) -> "list[int]":
    pattern = re.compile(rf"^{re.escape(name)}\.{locale}\.v(\d+)\.md$")
    found = (pattern.match(path.name) for path in DIR.iterdir())
    return sorted(int(m.group(1)) for m in found if m)


def load_prompt(name: str, locale: str, version: Optional[int] = None) -> Prompt:
    if locale not in LOCALES:
        locale = DEFAULT_LOCALE
    available = versions(name, locale)
    if not available:
        raise LookupError(f"no prompt {name!r} for locale {locale!r}")
    if version is None:
        version = available[-1]
    elif version not in available:
        raise LookupError(f"prompt {name!r}/{locale} has no version {version}")
    raw = (DIR / f"{name}.{locale}.v{version}.md").read_text(encoding="utf-8")
    return Prompt(name, locale, version, _COMMENT.sub("", raw).strip())
