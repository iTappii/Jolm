from datetime import date, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest

from app.admin.service import validate_tariff
from app.regions import default_region
from app.routing.costs import Tariff, calculate_cost, load_tariffs, recommend
from tests.conftest import ROOT
from tests.test_admin import logged_in

SEED = ROOT / "data" / "seed" / "transport_tariffs.sql"


@pytest.mark.parametrize(
    ("mode", "base", "per_minute", "per_km", "traffic", "expected"),
    [
        ("walk", 0, 0, 0, 1, (0, 0)),
        ("bus", 100, 0, 0, 1, (100, 100)),
        ("metro", 100, 0, 0, 1, (100, 100)),
        ("scooter", 100, 40, 0, 1, (160, 160)),
        ("taxi", 400, 30, 100, 1.6, (595, 952)),
        ("car", 0, 0, 25, 1.6, (38, 60)),
    ],
)
def test_calculate_cost(mode, base, per_minute, per_km, traffic, expected):
    tariff = Tariff(mode, Decimal(base), Decimal(per_minute), Decimal(per_km))
    assert calculate_cost(tariff, 1500, 90, traffic) == expected


def test_cost_rounds_decimal_float_half_up():
    tariff = Tariff("scooter", Decimal(0), Decimal(100), Decimal(0))
    assert calculate_cost(tariff, 0, 0.3) == (1, 1)


def test_recommend_balances_time_and_cost_and_prefers_short_walks():
    assert recommend([]) is None
    taxi = {"mode": "taxi", "duration_s": 600, "cost_kzt_max": 2000}
    bus = {"mode": "bus", "duration_s": 1200, "cost_kzt_max": 100}
    walk = {"mode": "walk", "duration_s": 900, "cost_kzt_max": 0}
    assert recommend([taxi, bus]) == 1
    assert recommend([bus, bus]) == 0
    assert recommend([taxi, bus, walk]) == 2
    fast_bus = {**bus, "duration_s": 300}
    assert recommend([fast_bus, walk]) == 1
    assert recommend([fast_bus, {**walk, "duration_s": 901}]) == 0


def test_validate_tariff_rejects_inapplicable_and_invalid_rates():
    values, errors = validate_tariff(
        {
            "mode": "bus",
            "valid_from": "2026-11-21",
            "base_kzt": "100,50",
            "per_min_kzt": "1",
            "per_km_kzt": "NaN",
            "source": "Пример",
        }
    )
    assert values["base_kzt"] == Decimal("100.50")
    assert set(errors) == {"per_min_kzt", "per_km_kzt"}


async def test_tariff_versions_seed_and_history(conn):
    seed = SEED.read_text(encoding="utf-8")
    await conn.execute(seed)
    await conn.execute(
        """
        INSERT INTO transport_tariffs (
            mode, valid_from, base_kzt, per_min_kzt, per_km_kzt, source
        ) VALUES
            ('bus', '2026-11-21', 110, 0, 0, 'First revision'),
            ('bus', '2026-11-21', 120, 0, 0, 'Second revision'),
            ('bus', '2026-11-22', 130, 0, 0, 'Future revision')
        """
    )
    await conn.execute(seed)

    before = await load_tariffs(conn, date(2026, 11, 20))
    assert before["bus"].base_kzt == 100
    assert before["bus"].approximate
    assert set(before) == {"walk", "scooter", "bus", "metro", "taxi", "car", "taxi_intercity"}
    assert (await load_tariffs(conn, date(2026, 11, 21)))["bus"].base_kzt == 120
    assert (await load_tariffs(conn, date(2026, 11, 22)))["bus"].base_kzt == 130

    for statement in (
        "UPDATE transport_tariffs SET base_kzt = 0",
        "DELETE FROM transport_tariffs",
        "TRUNCATE transport_tariffs",
    ):
        with pytest.raises(psycopg.IntegrityError, match="append-only"):
            async with conn.transaction():
                await conn.execute(statement)
    rows = await (await conn.execute("SELECT version_id FROM transport_tariffs")).fetchall()
    assert len(rows) == 10


async def test_admin_appends_tariffs(client, conn):
    assert (await client.get("/admin/tariffs")).status_code == 303
    csrf = await logged_in(client, conn)
    today = datetime.now(default_region().tz).date()
    form = {
        "mode": "bus",
        "valid_from": today.isoformat(),
        "base_kzt": "100",
        "per_min_kzt": "0",
        "per_km_kzt": "0",
        "approximate": "on",
        "source": "Пример",
    }
    assert (await client.post("/admin/tariffs", data=form)).status_code == 403
    form["csrf_token"] = csrf
    invalid = await client.post("/admin/tariffs", data={**form, "per_min_kzt": "1"})
    assert invalid.status_code == 422
    assert "Для этого вида транспорта укажите 0" in invalid.text
    assert (await client.post("/admin/tariffs", data=form)).status_code == 303
    second = {**form, "base_kzt": "120"}
    assert (await client.post("/admin/tariffs", data=second)).status_code == 303
    future = {**form, "valid_from": (today + timedelta(days=1)).isoformat()}
    assert (await client.post("/admin/tariffs", data=future)).status_code == 303
    page = await client.get("/admin/tariffs")
    assert page.status_code == 200
    assert all(label in page.text for label in ("Текущий", "Архив", "Будущий"))
    assert (await load_tariffs(conn, today))["bus"].base_kzt == 120
