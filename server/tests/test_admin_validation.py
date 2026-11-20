"""Unit tests for admin input validation (pure functions, no DB)."""

from datetime import time

from app.admin import auth, service


def place_form(**over):
    base = {"name_ru": "Парк", "kind": "venue", "status": "active", "popularity": "0"}
    base.update(over)
    return base


def test_place_ok_and_empty_strings_become_none():
    values, errors = service.validate_place(
        place_form(entry_price_kzt="1 500", name_en="  ", elevation_m="")
    )
    assert errors == {}
    assert values["entry_price_kzt"] == 1500
    assert values["name_en"] is None and values["elevation_m"] is None
    assert values["is_public"] is False


def test_place_needs_a_name():
    _, errors = service.validate_place(place_form(name_ru=""))
    assert "name_ru" in errors


def test_place_rejects_bad_numbers_and_enums():
    _, errors = service.validate_place(
        place_form(
            entry_price_kzt="-5",
            avg_check_kzt="abc",
            typical_visit_min="0",
            elevation_m="99999",
            popularity="-1",
            kind="bogus",
            status="deleted",
            setting="underwater",
            category_id="not-a-uuid",
        )
    )
    assert set(errors) == {
        "entry_price_kzt",
        "avg_check_kzt",
        "typical_visit_min",
        "elevation_m",
        "popularity",
        "kind",
        "status",
        "setting",
        "category_id",
    }


def test_place_text_length_limit():
    _, errors = service.validate_place(place_form(name_ru="x" * 301))
    assert "name_ru" in errors


def test_hours_day_multiple_intervals_sorted():
    intervals, err = service.parse_hours_day("14:00-18:00\n9:00-13:00")
    assert err is None
    assert intervals == [(time(9, 0), time(13, 0)), (time(14, 0), time(18, 0))]


def test_hours_day_overnight_and_round_clock():
    assert service.parse_hours_day("20:00-02:00") == ([(time(20, 0), time(2, 0))], None)
    assert service.parse_hours_day("круглосуточно") == ([(time(0, 0), time(23, 59))], None)
    assert service.parse_hours_day("") == ([], None)


def test_hours_day_errors():
    for bad in ("9-18", "25:00-26:00", "10:00-10:00", "09:00-13:00\n12:00-18:00"):
        intervals, err = service.parse_hours_day(bad)
        assert err and intervals == [], bad


def test_validate_hours_reports_per_weekday():
    result, errors = service.validate_hours({"hours_0": "09:00-18:00", "hours_3": "oops"})
    assert result == [(0, time(9, 0), time(18, 0))]
    assert list(errors) == ["hours_3"]


def test_format_hours_roundtrip():
    rows = [
        (1, time(9, 0), time(13, 0)),
        (1, time(14, 0), time(18, 0)),
        (2, time(8, 0), time(9, 0)),
    ]
    assert service.format_hours_day(rows, 1) == "09:00-13:00\n14:00-18:00"
    assert service.format_hours_day(rows, 0) == ""


def test_like_pattern_escapes_wildcards():
    assert service.like_pattern("  ") is None
    assert service.like_pattern("50%_off\\") == "%50\\%\\_off\\\\%"


def test_event_validation():
    form = {"title_ru": "Концерт", "starts_at": "2026-12-01T19:00", "ends_at": "2026-12-01T21:00"}
    values, errors = service.validate_event(form)
    assert errors == {} and values["is_promoted"] is False
    _, errors = service.validate_event(dict(form, ends_at="2026-12-01T18:00"))
    assert "ends_at" in errors
    _, errors = service.validate_event({"title_ru": "", "starts_at": "garbage"})
    assert {"title_ru", "starts_at"} <= set(errors)
    _, errors = service.validate_event(dict(form, price_kzt="-1", place_id="zzz"))
    assert {"price_kzt", "place_id"} <= set(errors)


def test_route_and_category_validation():
    _, errors = service.validate_route({"title_ru": "", "title_en": "x"})
    assert "title_ru" in errors
    values, errors = service.validate_category({"name_ru": "a", "name_en": "b", "outdoor": "on"})
    assert errors == {} and values["outdoor"] is True and values["sort_order"] == 0


def test_storage_key():
    assert service.validate_storage_key("photos/a.jpg") == ("photos/a.jpg", None)
    assert service.validate_storage_key("http://x/a.jpg")[1]
    assert service.validate_storage_key("has space")[1]
    assert service.validate_storage_key("")[1]


def test_password_hashing_and_policy():
    encoded = auth.hash_password("correct horse battery")
    assert encoded.startswith("$argon2id$")
    assert auth.verify_password(encoded, "correct horse battery")
    assert not auth.verify_password(encoded, "wrong")
    assert not auth.verify_password("garbage", "x")
    assert auth.password_error("short")
    assert auth.password_error("long enough password") is None


def test_csrf_token_is_per_session_and_deterministic():
    assert auth.csrf_for_session("a") == auth.csrf_for_session("a")
    assert auth.csrf_for_session("a") != auth.csrf_for_session("b")
    assert not auth.tokens_equal(None, "x")
    assert auth.tokens_equal("x", "x")
