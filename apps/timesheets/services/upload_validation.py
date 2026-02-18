import calendar as _calendar
from datetime import date as _date, timedelta as _timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .upload_parser import REQUIRED_SHEETS


ERROR = "ERROR"
WARN = "WARN"


def _first_workday_on_or_after(d):
    """Return *d* itself if it's Mon-Fri, otherwise the following Monday."""
    while d.weekday() >= 5:
        d += _timedelta(days=1)
    return d


def _submission_windows_for_today(today=None):
    """
    Return the set of (year, month) values that are valid upload targets
    right now.

    Timesheets are submitted en masse once the period is complete:
      * 1st-half (days 1-15): window opens on the 15th, due on the first
        business day on or after the 15th.
      * 2nd-half (days 16-end): window opens on the 1st of the next month,
        due on the first business day on or after the 1st of the next month.

    A grace period (UPLOAD_GRACE_CALENDAR_DAYS, default 10) extends the
    window past the due date.
    """
    if today is None:
        today = timezone.localdate()

    valid = set()
    grace_calendar_days = getattr(settings, "UPLOAD_GRACE_CALENDAR_DAYS", 10)

    for delta_months in (-1, 0, 1):
        probe_year = today.year + (today.month - 1 + delta_months) // 12
        probe_month = (today.month - 1 + delta_months) % 12 + 1

        first_half_due = _first_workday_on_or_after(_date(probe_year, probe_month, 15))
        first_half_open = _date(probe_year, probe_month, 15)
        first_half_close = first_half_due + _timedelta(days=grace_calendar_days)

        if probe_month == 12:
            next_month_1st = _date(probe_year + 1, 1, 1)
        else:
            next_month_1st = _date(probe_year, probe_month + 1, 1)

        second_half_due = _first_workday_on_or_after(next_month_1st)
        second_half_open = next_month_1st
        second_half_close = second_half_due + _timedelta(days=grace_calendar_days)

        if first_half_open <= today <= first_half_close:
            valid.add((probe_year, probe_month))
        if second_half_open <= today <= second_half_close:
            valid.add((probe_year, probe_month))

    return valid


def _open_halves_for_today(year, month, today=None):
    """
    Return a set of half-keys ("first_half", "second_half") whose submission
    windows are currently open for the given (year, month).
    """
    if today is None:
        today = timezone.localdate()

    grace_calendar_days = getattr(settings, "UPLOAD_GRACE_CALENDAR_DAYS", 10)
    halves = set()

    first_half_open = _date(year, month, 15)
    first_half_due = _first_workday_on_or_after(first_half_open)
    first_half_close = first_half_due + _timedelta(days=grace_calendar_days)

    if month == 12:
        next_month_1st = _date(year + 1, 1, 1)
    else:
        next_month_1st = _date(year, month + 1, 1)

    second_half_open = next_month_1st
    second_half_due = _first_workday_on_or_after(second_half_open)
    second_half_close = second_half_due + _timedelta(days=grace_calendar_days)

    if first_half_open <= today <= first_half_close:
        halves.add("first_half")
    if second_half_open <= today <= second_half_close:
        halves.add("second_half")

    return halves


def validate_parsed_workbook(parsed):
    issues = []
    sheets_present = set(parsed.get("sheets_present") or [])
    missing = [name for name in REQUIRED_SHEETS if name not in sheets_present]
    if missing:
        for name in missing:
            _add_issue(
                issues,
                ERROR,
                "STRUCTURE_MISSING_SHEET",
                f"Missing required sheet: {name}",
                location=name,
                hint="Download a fresh template and re-upload.",
            )

    metadata = parsed.get("metadata") or {}
    year = parsed.get("period", {}).get("year")
    month = parsed.get("period", {}).get("month")

    if not year or not month:
        _add_issue(
            issues,
            ERROR,
            "STRUCTURE_MISSING_CELL",
            "Missing year or month in the template header.",
            location="Time-1st half of month!T1/V1",
            hint="Check the template header cells and re-upload.",
        )
    elif not (1 <= int(month) <= 12) or int(year) < 2000:
        _add_issue(
            issues,
            ERROR,
            "STRUCTURE_INVALID_PERIOD",
            f"Invalid period: {year}-{month}",
            location="Time-1st half of month!T1/V1",
            hint="Ensure the month/year are correct in the template.",
        )
    else:
        valid_windows = _submission_windows_for_today()
        if (int(year), int(month)) not in valid_windows:
            from calendar import month_name
            _add_issue(
                issues,
                ERROR,
                "PERIOD_OUTSIDE_SUBMISSION_WINDOW",
                f"This workbook is for {month_name[int(month)]} {year}, which is outside "
                f"the current submission window.",
                location="Time-1st half of month!T1/V1",
                hint="Upload the timesheet for the current period, or contact "
                     "your office manager if you need a late submission.",
            )

    template_version = metadata.get("template_version", "")
    if template_version and "Version" not in template_version:
        _add_issue(
            issues,
            WARN,
            "STRUCTURE_UNKNOWN_TEMPLATE_VERSION",
            "Template version does not look like a known signature.",
            location="Time-1st half of month!A39",
            hint="Confirm you used the latest template.",
        )

    open_halves = set()
    if year and month:
        open_halves = _open_halves_for_today(int(year), int(month))

    _validate_time_half(parsed.get("time", {}).get("first_half"), issues,
                        "Time-1st half of month", enforce_minimums="first_half" in open_halves)
    _validate_time_half(parsed.get("time", {}).get("second_half"), issues,
                        "Time-2nd half of month", enforce_minimums="second_half" in open_halves)

    _validate_expenses(parsed, issues)
    _validate_cross_checks(parsed, issues)

    return issues


def _validate_time_half(half_data, issues, sheet_name, enforce_minimums=True):
    if not half_data:
        return

    total_hours = Decimal(str(half_data.get("total_hours", 0)))
    half_has_hours = total_hours > 0

    min_weekday_hours = Decimal(str(getattr(settings, "MIN_WEEKDAY_HOURS", 8)))
    increment_minutes = getattr(settings, "TIME_INCREMENT_MINUTES", 15)
    increment = Decimal(str(increment_minutes)) / Decimal("60")

    minimum_severity = ERROR if enforce_minimums else WARN

    for line in half_data.get("lines", []):
        row_total = Decimal(str(line.get("row_total", 0)))
        charge_code = (line.get("charge_code") or "").strip()
        category = (line.get("category") or "").strip()
        group = line.get("group")

        if group == "client" and row_total > 0 and not charge_code:
            _add_issue(
                issues,
                minimum_severity,
                "TIME_MISSING_CHARGE_CODE",
                "Hours entered without a client charge code.",
                location=f"{sheet_name}!U{line.get('row')}",
                hint="Add a charge code for this row.",
            )

        if group == "marketing" and row_total > 0:
            if not category or category.lower() == "select category":
                _add_issue(
                    issues,
                    minimum_severity,
                    "TIME_MARKETING_CATEGORY_NOT_SELECTED",
                    "Marketing row has hours but no category selected.",
                    location=f"{sheet_name}!A{line.get('row')}",
                    hint="Select a marketing category from the dropdown.",
                )

        for day_str, hours in line.get("hours_by_day", {}).items():
            hours_decimal = Decimal(str(hours))
            if hours_decimal < 0:
                _add_issue(
                    issues,
                    ERROR,
                    "TIME_NEGATIVE_HOURS",
                    "Negative hours entered.",
                    location=f"{sheet_name}!{line.get('row')}",
                    hint="Hours must be zero or positive.",
                )
            if hours_decimal % increment != 0:
                _add_issue(
                    issues,
                    WARN,
                    "TIME_NONSTANDARD_INCREMENT",
                    f"Hours not in {increment_minutes}-minute increments.",
                    location=f"{sheet_name}!{line.get('row')}",
                    hint=f"Use {increment_minutes}-minute increments where possible.",
                )

    for day_str, total in (half_data.get("daily_totals") or {}).items():
        hours = Decimal(str(total))
        day = _parse_date_str(day_str)
        if not day:
            continue
        if half_has_hours and day.weekday() < 5 and hours < min_weekday_hours:
            _add_issue(
                issues,
                minimum_severity,
                "TIME_DAILY_MINIMUM_NOT_MET",
                f"Weekday total is below minimum: {hours} hours.",
                location=f"{sheet_name}!{day.isoformat()}",
                hint="Ensure weekday hours meet the minimum requirement.",
            )
        if hours > 24:
            _add_issue(
                issues,
                ERROR,
                "TIME_DAY_EXCEEDS_24",
                "Daily total exceeds 24 hours.",
                location=f"{sheet_name}!{day.isoformat()}",
                hint="Adjust hours so the daily total is realistic.",
            )


def _validate_expenses(parsed, issues):
    expenses = parsed.get("expenses", {})
    items = expenses.get("items", [])

    expected_codes = _build_expected_codes(parsed)

    for item in items:
        amount = Decimal(str(item.get("amount", 0)))
        if amount <= 0:
            continue
        if not item.get("charge_code"):
            _add_issue(
                issues,
                WARN,
                "EXPENSE_MISSING_CHARGE_CODE",
                "Expense amount entered without a charge code.",
                location=f"{item.get('sheet')}!V{item.get('row')}",
                hint="Add a charge code for this expense row.",
            )
        if not item.get("date"):
            _add_issue(
                issues,
                WARN,
                "EXPENSE_MISSING_DATE",
                "Expense amount entered without a date.",
                location=f"{item.get('sheet')}!A{item.get('row')}",
                hint="Add a date for this expense row.",
            )
        if not item.get("description"):
            _add_issue(
                issues,
                WARN,
                "EXPENSE_MISSING_DESCRIPTION",
                "Expense amount entered without a description.",
                location=f"{item.get('sheet')}!B{item.get('row')}",
                hint="Add a description for this expense row.",
            )

        charge_code = item.get("charge_code")
        if charge_code and expected_codes and charge_code not in expected_codes:
            _add_issue(
                issues,
                WARN,
                "EXPENSE_UNKNOWN_CHARGE_CODE",
                f"Charge code {charge_code} does not match any time sheet line.",
                location=f"{item.get('sheet')}!V{item.get('row')}",
                hint="Use a charge code that appears in your time sheet.",
            )


def _validate_cross_checks(parsed, issues):
    expenses = parsed.get("expenses", {})
    totals_by_code = expenses.get("totals_by_charge_code", {})
    tolerance = Decimal(str(getattr(settings, "AGGREGATION_ROUNDING_TOLERANCE", 0.01)))

    marketing_total = Decimal(str(expenses.get("marketing_total", 0)))
    keystone_paid_total = Decimal(str(expenses.get("keystone_paid_total", 0)))
    client_billed_total = Decimal(str(expenses.get("client_billed_total", 0)))
    total_expenses = Decimal(str(expenses.get("total_expenses", 0)))

    expected = _build_expected_codes(parsed, include_marketing=True)
    marketing_codes = {code for code in expected if code.endswith("-LEAD") or code.endswith("-OTHER")}
    client_codes = _build_client_codes(parsed)
    internal_codes = _build_internal_codes()

    marketing_code_total = _sum_codes(totals_by_code, marketing_codes)
    if abs(marketing_code_total - marketing_total) > tolerance:
        _add_issue(
            issues,
            WARN,
            "EXPENSE_MARKETING_ALLOCATION_MISMATCH",
            "Marketing expenses do not reconcile with marketing charge codes.",
            location="Expenses-Main/Additional",
            hint="Ensure marketing expenses use *-LEAD or *-OTHER codes.",
        )

    if client_billed_total > 0:
        client_code_total = _sum_codes(totals_by_code, client_codes)
        if abs(client_code_total - client_billed_total) > tolerance:
            _add_issue(
                issues,
                WARN,
                "EXPENSE_CLIENT_BILLED_MISMATCH",
                "Client-billed expenses do not reconcile with client charge codes.",
                location="Expenses-Main/Additional",
                hint="Code client-billed amounts to client charge codes.",
            )

    internal_code_total = _sum_codes(totals_by_code, internal_codes.union(marketing_codes))
    if abs(internal_code_total - keystone_paid_total) > tolerance:
        _add_issue(
            issues,
            WARN,
            "EXPENSE_KEYSTONE_PAID_MISMATCH",
            "Keystone-paid expenses do not reconcile with internal codes.",
            location="Expenses-Main/Additional",
            hint="Ensure internal expenses use ADM/MTG/REC/TRN/HOL/PTO/OFF or marketing codes.",
        )

    all_code_total = _sum_codes(totals_by_code, totals_by_code.keys())
    if abs(all_code_total - total_expenses) > tolerance:
        _add_issue(
            issues,
            WARN,
            "EXPENSE_TOTAL_MISMATCH",
            "Total expenses do not reconcile with coded expenses.",
            location="Expenses-Main/Additional",
            hint="Check for missing or mis-typed charge codes.",
        )


def _build_expected_codes(parsed, include_marketing=False):
    codes = set()
    codes.update(_build_client_codes(parsed))
    codes.update(_build_internal_codes())
    if include_marketing:
        codes.update(_build_marketing_codes(parsed))
    return codes


def _build_client_codes(parsed):
    codes = set()
    for half in ("first_half", "second_half"):
        totals = parsed.get("time", {}).get(half, {}).get("totals_by_client_code", {})
        codes.update([code for code in totals.keys() if code])
    return codes


def _build_marketing_codes(parsed):
    codes = set()
    for half in ("first_half", "second_half"):
        totals = parsed.get("time", {}).get(half, {}).get("totals_by_marketing_bucket", {})
        for base in totals.keys():
            if base:
                codes.add(f"{base}-LEAD")
                codes.add(f"{base}-OTHER")
    return codes


def _build_internal_codes():
    return {"ADM", "MTG", "REC", "TRN", "HOL", "PTO", "OFF"}


def _sum_codes(totals_by_code, codes):
    total = Decimal("0")
    for code in codes:
        if code in totals_by_code:
            total += Decimal(str(totals_by_code[code]))
    return total


def _parse_date_str(value):
    try:
        return None if not value else _date.fromisoformat(value)
    except ValueError:
        return None


def _add_issue(issues, severity, code, message, location="", hint=""):
    issues.append({
        "severity": severity,
        "code": code,
        "message": message,
        "location": location,
        "hint": hint,
    })
