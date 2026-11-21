"""TEMPORARY bonus formula (Ш-46, SSOT §10.3). OPEN(SSOT §16.8): the real formula is undecided.

Only the principle is decided: 1 bonus ~ 1 tenge, and the amount depends mainly on the demand
coefficient, "how much this data about the place is needed right now". Until the owner decides,
this module is the ONE place with the formula; the constants live in the `demand_coefficients`
table (admin panel "Бонусы") and fall back to DEFAULTS here. Pure functions, no database.

    amount = round(base[type] * age_factor * freq_factor)           (at least 1)

    age_factor  = age_min + (age_max - age_min) * min(field_age_days / age_full_days, 1)
        field_age_days = how old the data field this submission improves is (menu: place_menu,
        photo: newest photo, price: the place record, review: newest review). A field with no data
        at all counts as the oldest (age_max). Fresh data -> age_min.
    freq_factor = freq_min + (freq_max - freq_min) * min(trips / freq_full_trips, 1)
        trips = number of trips in the last `freq_window_days` days that contain the place.
    transit data is not about one place: both factors are 1.

Not here, on purpose (undecided): daily caps, quality bonuses, streaks, spending.
"""

from dataclasses import dataclass
from typing import Dict, Mapping, Optional

MAX_BONUS = 100_000  # absolute ceiling per submission, whatever the constants say


@dataclass(frozen=True)
class Param:
    default: float
    low: float
    high: float
    label: str


DEFAULTS: Dict[str, Param] = {
    "base_review": Param(20, 0, 10_000, "Базовый бонус: отзыв, бонусов"),
    "base_photo": Param(50, 0, 10_000, "Базовый бонус: фото, бонусов"),
    "base_menu": Param(100, 0, 10_000, "Базовый бонус: меню, бонусов"),
    "base_price": Param(40, 0, 10_000, "Базовый бонус: цена входа, бонусов"),
    "base_transit": Param(60, 0, 10_000, "Базовый бонус: данные о транспорте, бонусов"),
    "age_full_days": Param(180, 1, 3650, "Возраст данных для полного коэффициента давности, дней"),
    "age_min": Param(0.5, 0, 10, "Коэффициент давности для свежих данных"),
    "age_max": Param(2, 0, 10, "Коэффициент давности для устаревших или отсутствующих данных"),
    "freq_window_days": Param(90, 1, 3650, "Окно подсчёта поездок, дней"),
    "freq_full_trips": Param(20, 1, 100_000, "Поездок в окне для полного коэффициента частоты"),
    "freq_min": Param(1, 0, 10, "Коэффициент частоты: место не попадает в маршруты"),
    "freq_max": Param(2, 0, 10, "Коэффициент частоты: место часто в маршрутах"),
}  # fmt: skip

TYPES = ("review", "photo", "menu", "price", "transit")


@dataclass(frozen=True)
class Breakdown:
    amount: int
    base: float
    age_factor: float
    freq_factor: float

    def as_json(self, field_age_days: Optional[float], trips: int) -> dict:
        return {
            "base": self.base,
            "age_factor": self.age_factor,
            "freq_factor": self.freq_factor,
            "field_age_days": None if field_age_days is None else round(field_age_days, 1),
            "trips": trips,
        }


def resolve(stored: Mapping[str, float]) -> Dict[str, float]:
    """Constants in force: the stored value, else the default."""
    return {key: float(stored.get(key, p.default)) for key, p in DEFAULTS.items()}


def validate(raw: Mapping[str, str]):
    """Admin form -> ({key: float}, {key: error}). Every key is required."""
    values: Dict[str, float] = {}
    errors: Dict[str, str] = {}
    for key, p in DEFAULTS.items():
        text = (raw.get(key) or "").strip().replace(",", ".")
        try:
            number = float(text)
        except ValueError:
            errors[key] = "Введите число"
            continue
        if not (p.low <= number <= p.high) or number != number:
            errors[key] = "Допустимо от %g до %g" % (p.low, p.high)
            continue
        values[key] = round(number, 3)
    for low, high in (("age_min", "age_max"), ("freq_min", "freq_max")):
        if low in values and high in values and values[low] > values[high]:
            errors[low] = "Не больше максимума"
    return values, errors


def compute(
    type_: str, coeffs: Mapping[str, float], field_age_days: Optional[float], trips: int
) -> Breakdown:
    base = coeffs["base_" + type_]
    if type_ == "transit":
        age_factor = freq_factor = 1.0
    else:
        if field_age_days is None:  # nothing known about this field yet: the data is needed most
            age_factor = coeffs["age_max"]
        else:
            share = min(max(field_age_days, 0.0) / coeffs["age_full_days"], 1.0)
            age_factor = coeffs["age_min"] + (coeffs["age_max"] - coeffs["age_min"]) * share
        share = min(max(trips, 0) / coeffs["freq_full_trips"], 1.0)
        freq_factor = coeffs["freq_min"] + (coeffs["freq_max"] - coeffs["freq_min"]) * share
    raw = base * age_factor * freq_factor
    amount = 0 if base <= 0 else min(max(1, int(raw + 0.5)), MAX_BONUS)
    return Breakdown(amount, base, round(age_factor, 3), round(freq_factor, 3))
