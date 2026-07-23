from datetime import date

from app.tasks.reports import _monthly_period, _weekly_period


def test_weekly_period_covers_seven_full_days_ending_yesterday() -> None:
    start, end = _weekly_period(date(2026, 7, 23))
    assert end == date(2026, 7, 22)
    assert start == date(2026, 7, 16)
    assert (end - start).days == 6


def test_monthly_period_covers_full_month() -> None:
    start, end = _monthly_period(date(2026, 7, 23))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 7, 31)


def test_monthly_period_handles_december_year_rollover() -> None:
    start, end = _monthly_period(date(2026, 12, 15))
    assert start == date(2026, 12, 1)
    assert end == date(2026, 12, 31)


def test_monthly_period_handles_february() -> None:
    start, end = _monthly_period(date(2026, 2, 10))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)
