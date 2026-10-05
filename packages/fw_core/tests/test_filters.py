"""Filter matching and schedule windows (pure logic, no services)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from fw_core.filters import ANY, Filter, Schedule, active, first_match, parse_windows

JOB = {"origin": "Dallas, TX", "destination": "Memphis, TN", "rate_usd": 1800, "equipment": "Van", "weight_lb": 30000}


def f(**kw: object) -> Filter:
    base: dict[str, object] = {
        "id": uuid4(),
        "name": "f",
        "origin": ANY,
        "destination": ANY,
        "min_rate_usd": 0,
        "equipment": frozenset(),
        "max_weight_lb": 80000,
        "account_group": "default",
    }
    return Filter(**{**base, **kw})  # type: ignore[arg-type]


def test_each_criterion_can_reject() -> None:
    assert f().matches(JOB)
    assert f(origin="Dallas, TX", destination="Memphis, TN", equipment=frozenset({"Van", "Reefer"})).matches(JOB)
    assert not f(origin="Austin, TX").matches(JOB)
    assert not f(destination="Atlanta, GA").matches(JOB)
    assert not f(min_rate_usd=1801).matches(JOB)
    assert not f(equipment=frozenset({"Flatbed"})).matches(JOB)
    assert not f(max_weight_lb=29999).matches(JOB)


def test_first_match_in_order() -> None:
    a, b = f(name="a", min_rate_usd=5000), f(name="b")
    assert first_match([a, b], JOB) is b
    assert first_match([a], JOB) is None


def test_schedule_windows_including_overnight_and_timezone() -> None:
    day = parse_windows([{"days": [0, 1, 2, 3, 4], "start": "06:00", "end": "18:00"}])
    night = parse_windows([{"days": [4], "start": "22:00", "end": "02:00"}])  # Friday night into Saturday
    weekday, night_filter, free = f(name="weekday"), f(name="night"), f(name="free")
    schedules = [
        Schedule(uuid4(), "America/Chicago", day, frozenset({weekday.id})),
        Schedule(uuid4(), "America/Chicago", night, frozenset({night_filter.id})),
    ]
    filters = [weekday, night_filter, free]
    # Monday 2026-10-05 15:00 UTC = 10:00 Chicago (CDT)
    assert {x.name for x in active(filters, schedules, datetime(2026, 10, 5, 15, tzinfo=UTC))} == {"weekday", "free"}
    # Monday 12:00 UTC = 07:00 Chicago is inside; 10:59 UTC = 05:59 is not
    assert "weekday" not in {x.name for x in active(filters, schedules, datetime(2026, 10, 5, 10, 59, tzinfo=UTC))}
    # Saturday 2026-10-10 06:30 UTC = 01:30 Chicago: still Friday's overnight window
    assert {x.name for x in active(filters, schedules, datetime(2026, 10, 10, 6, 30, tzinfo=UTC))} == {"night", "free"}
    # Saturday 07:30 UTC = 02:30 Chicago: window closed
    assert {x.name for x in active(filters, schedules, datetime(2026, 10, 10, 7, 30, tzinfo=UTC))} == {"free"}


def test_bad_windows_are_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_windows([{"days": [7], "start": "06:00", "end": "07:00"}])
    with pytest.raises(ValidationError):
        parse_windows([{"days": [], "start": "06:00", "end": "07:00"}])
