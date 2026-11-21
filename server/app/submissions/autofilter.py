"""Auto-filter of submissions (Ш-45, SSOT §10.2): garbage is cut at once, the rest is published
"to be checked later" and waits in the moderation queue.

Pure rules over the payload plus three database lookups (duplicate text, duplicate photo hash,
the place's known prices). Every rule yields a machine code; any code means `rejected_auto`
(no bonus, nothing shown to others). Codes:

    too_short            review text under 10 characters (a rating alone is fine)
    no_letters           a review text with no letters at all ("!!!!!!!!!!", "1234567890")
    repeated_text        one character repeated 8+ times, or one word dominating the text
    contains_link        URL, domain name, messenger link or e-mail address
    contains_contact     a phone number
    profanity            a word of `profanity.txt` (RU / EN / KZ seed list)
    duplicate_text       the same review text already published for the place, or sent by the
                         same person within 30 days
    duplicate_photo      the same image bytes (sha256) are already published or waiting
    rejected_photo       the same image bytes were rejected by a moderator before
    implausible_price    a price outside a plausible range or far from the place's known price

Not done (Ш-45 says optional): LLM classification of "is this a real review". The rules do not
catch fluent, relevant-looking spam or fake praise; that is what the moderation queue is for.
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID

from app.db import fetch_one

REVIEW_MIN_CHARS = 10
REPEAT_CHAR_RUN = 8
DOMINANT_WORD_SHARE = 0.6  # a word making up this share of 5+ words
DUPLICATE_WINDOW_DAYS = 30
ENTRY_PRICE_MAX = 200_000
DISH_PRICE_RANGE = (50, 100_000)
TRANSIT_PRICE_MAX = 5_000
KNOWN_PRICE_FACTOR = 10  # an entry price this many times above / below the known one is implausible
PROFANITY_FILE = Path(__file__).with_name("profanity.txt")

_URL = re.compile(
    r"(https?://|www\.|\bt\.me/|\bwa\.me/|\b[\w.+-]+@[\w-]+\.\w{2,}|"
    r"\b[\w-]{2,}\.(com|net|org|info|biz|xyz|ru|kz|su|me|io|ly|tk|ua|by|uz|app|shop|site|online|"
    r"link|click|top|club|pro)\b)",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_RUN = re.compile(r"(.)\1+")


@dataclass
class FilterResult:
    passed: bool
    reasons: List[str] = field(default_factory=list)  # machine codes, see the module docstring

    def as_json(self) -> Dict[str, Any]:
        return {"passed": self.passed, "reasons": self.reasons, "version": 1}


# --- text rules -------------------------------------------------------------------------------


def collapse(word: str) -> str:
    """Lower-case, ё -> е, every run of one repeated letter shortened to a single letter."""
    return _RUN.sub(r"\1", word.lower().replace("ё", "е"))


@lru_cache(maxsize=1)
def profanity_lists(path: Path = PROFANITY_FILE) -> Tuple[Tuple[str, ...], frozenset]:
    prefixes, exact = [], set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        kind, _, word = line.partition(" ")
        word = collapse(word.strip())
        if kind == "prefix" and word:
            prefixes.append(word)
        elif kind == "exact" and word:
            exact.add(word)
    return tuple(prefixes), frozenset(exact)


def has_profanity(text: str) -> bool:
    prefixes, exact = profanity_lists()
    for token in _WORD.findall(text):
        word = collapse(token)
        if word in exact or any(word.startswith(p) for p in prefixes):
            return True
    return False


def text_reasons(text: str, need_letters: bool = False) -> List[str]:
    out = []
    words = [w.lower() for w in _WORD.findall(text)]
    if need_letters and not words:
        out.append("no_letters")
    if _URL.search(text):
        out.append("contains_link")
    if _PHONE.search(text):
        out.append("contains_contact")
    if has_profanity(text):
        out.append("profanity")
    repeated_char = re.search(r"(.)\1{%d,}" % (REPEAT_CHAR_RUN - 1), text) is not None
    dominant = False
    if len(words) >= 5:
        top = max(words.count(w) for w in set(words))
        dominant = top / len(words) >= DOMINANT_WORD_SHARE
    if repeated_char or dominant:
        out.append("repeated_text")
    return out


def free_texts(type_: str, payload: Dict[str, Any]) -> List[str]:
    """Every user-written string of a payload, for the text rules."""
    out: List[Optional[str]] = []
    if type_ == "review":
        out.append(payload.get("text"))
    elif type_ == "menu":
        for item in payload.get("items", []):
            out += [item.get("name"), item.get("description")]
    elif type_ == "photo":
        out.append(payload.get("caption"))
    elif type_ == "transit":
        out += [payload.get("route_ref"), payload.get("stop"), payload.get("direction")]
        out.append(payload.get("note"))
    elif type_ == "price":
        out.append(payload.get("note"))
    return [t for t in out if t]


def price_reasons(
    type_: str, payload: Dict[str, Any], known_entry_price: Optional[int]
) -> List[str]:
    bad = False
    if type_ == "price":
        price = payload["price_kzt"]
        bad = price > ENTRY_PRICE_MAX
        if known_entry_price and known_entry_price > 0:
            bad = bad or price > known_entry_price * KNOWN_PRICE_FACTOR
            # a cheaper ticket (child, student...) or a free day is normal; an adult / foreigner
            # price a tenth of the known one is not
            if payload.get("audience", "adult") in ("adult", "foreigner", "resident"):
                bad = bad or 0 < price * KNOWN_PRICE_FACTOR < known_entry_price
    elif type_ == "menu":
        low, high = DISH_PRICE_RANGE
        bad = any(
            i.get("price_kzt") is not None and not low <= i["price_kzt"] <= high
            for i in payload.get("items", [])
        )
    elif type_ == "transit":
        price = payload.get("price_kzt")
        bad = price is not None and price > TRANSIT_PRICE_MAX
    return ["implausible_price"] if bad else []


# --- the filter -------------------------------------------------------------------------------


async def evaluate(
    conn,
    *,
    type: str,
    payload: Dict[str, Any],
    user_id: UUID,
    place_id: Optional[UUID],
    content_hash: Optional[str],
) -> FilterResult:
    reasons: List[str] = []

    def add(codes: Iterable[str]) -> None:
        reasons.extend(c for c in codes if c not in reasons)

    for text in free_texts(type, payload):
        add(text_reasons(text, need_letters=type == "review"))
    if type == "review":
        text = payload.get("text")
        if text and len(text) < REVIEW_MIN_CHARS:
            add(["too_short"])
        if text:
            again = await fetch_one(
                conn,
                """
                SELECT 1 AS ok FROM submissions
                WHERE type = 'review' AND lower(payload->>'text') = lower(%s)
                  AND status IN ('published_pending_review', 'approved')
                  AND (place_id = %s
                       OR (user_id = %s AND created_at > now() - make_interval(days => %s)))
                LIMIT 1
                """,
                (text, place_id, user_id, DUPLICATE_WINDOW_DAYS),
            )
            if again:
                add(["duplicate_text"])
    if content_hash:
        same = await fetch_one(
            conn,
            """
            SELECT bool_or(status IN ('published_pending_review', 'approved')) AS live,
                   bool_or(status = 'rejected') AS moderated_out
            FROM submissions WHERE content_hash = %s
            """,
            (content_hash,),
        )
        if same and same["live"]:
            add(["duplicate_photo"])
        elif same and same["moderated_out"]:
            add(["rejected_photo"])
    if type in ("price", "menu", "transit"):
        known = None
        if type == "price" and place_id is not None:
            row = await fetch_one(
                conn, "SELECT entry_price_kzt FROM places WHERE id = %s", (place_id,)
            )
            known = row["entry_price_kzt"] if row else None
        add(price_reasons(type, payload, known))
    return FilterResult(not reasons, reasons)
