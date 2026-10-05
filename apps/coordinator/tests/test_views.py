"""Schedule windows become whole-hour spans on the console's week grid (0 = Monday)."""

from fw_coordinator.views import _hour_cells


def test_a_daytime_window_is_one_span() -> None:
    assert _hour_cells(0, "06:00", "20:00") == [{"day": 0, "start_hour": 6, "end_hour": 20}]


def test_a_partial_end_hour_is_drawn_whole() -> None:
    assert _hour_cells(2, "09:00", "17:30") == [{"day": 2, "start_hour": 9, "end_hour": 18}]


def test_an_overnight_window_continues_next_day_and_sunday_wraps_to_monday() -> None:
    assert _hour_cells(6, "22:00", "06:00") == [
        {"day": 6, "start_hour": 22, "end_hour": 24},
        {"day": 0, "start_hour": 0, "end_hour": 6},
    ]


def test_a_window_ending_at_midnight_stays_on_its_day() -> None:
    assert _hour_cells(4, "18:00", "00:00") == [{"day": 4, "start_hour": 18, "end_hour": 24}]
