"""The built-in first region: the same values as the row of migration 0029.

Used until the regions are loaded from the database (unit tests that never open it, the first
moments of a process). A test compares it with the database row, so the two cannot drift apart.
This is the data of a region, not a city constant of the code: nothing outside `app/regions`
names it.
"""

from app.regions.model import Region

ALMATY = Region(
    id="almaty",
    name_ru="Алматы",
    name_en="Almaty",
    timezone="Asia/Almaty",
    currency="KZT",
    languages=("ru", "en"),
    centre=(43.2389, 76.9455),
    zoom=11.0,
    bbox=(76.70, 42.95, 77.30, 43.45),
    is_default=True,
)
