"""
Office Manager review dashboard and approval workflow.
Managing Partner and Payroll Partner views.
"""
import csv
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from io import BytesIO, StringIO

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

from apps.timesheets.models import Timesheet, TimesheetLine, TimeEntry, ChargeCode
from apps.expenses.models import ExpenseReport, ExpenseCategory, ExpenseItem
from apps.periods.models import TimesheetPeriod, ExpenseMonth
from apps.accounts.models import User, EmployeeProfile
from .models import ReviewAction, ReviewComment


def office_manager_required(view_func):
    """Decorator to require office_manager or higher role."""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not request.user.groups.filter(
            name__in=["office_manager", "managing_partner", "payroll_partner"]
        ).exists() and not request.user.is_superuser:
            return HttpResponseForbidden("Access denied. Office Manager role required.")
        return view_func(request, *args, **kwargs)
    return wrapped


def managing_partner_required(view_func):
    """Decorator to require managing_partner role."""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not request.user.groups.filter(
            name="managing_partner"
        ).exists() and not request.user.is_superuser:
            return HttpResponseForbidden("Access denied. Managing Partner role required.")
        return view_func(request, *args, **kwargs)
    return wrapped


def payroll_partner_required(view_func):
    """Decorator to require payroll_partner role."""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not request.user.groups.filter(
            name__in=["payroll_partner", "managing_partner"]
        ).exists() and not request.user.is_superuser:
            return HttpResponseForbidden("Access denied. Payroll Partner role required.")
        return view_func(request, *args, **kwargs)
    return wrapped


@login_required
@office_manager_required
def review_dashboard(request):
    """Office Manager dashboard: submission status overview."""
    # Get active periods
    current_ts_period = TimesheetPeriod.get_current_period()
    current_expense_month = ExpenseMonth.get_current_month()

    # Get recent periods for filtering
    recent_ts_periods = TimesheetPeriod.objects.order_by("-year", "-month", "-half")[:6]
    recent_expense_months = ExpenseMonth.objects.order_by("-year", "-month")[:3]

    # Get selected period from query params
    ts_period_id = request.GET.get("ts_period")
    expense_month_id = request.GET.get("expense_month")

    selected_ts_period = None
    selected_expense_month = None

    if ts_period_id:
        selected_ts_period = TimesheetPeriod.objects.filter(pk=ts_period_id).first()
    elif current_ts_period:
        selected_ts_period = current_ts_period

    if expense_month_id:
        selected_expense_month = ExpenseMonth.objects.filter(pk=expense_month_id).first()
    elif current_expense_month:
        selected_expense_month = current_expense_month

    # Get all active employees
    active_employees = User.objects.filter(
        is_active=True,
        groups__name="employees"
    ).select_related("profile").distinct()

    # Timesheet status for selected period
    ts_status = []
    if selected_ts_period:
        for emp in active_employees:
            try:
                ts = Timesheet.objects.get(employee=emp, period=selected_ts_period)
                ts_status.append({
                    "employee": emp,
                    "timesheet": ts,
                    "status": ts.status,
                    "hours": ts.total_hours,
                })
            except Timesheet.DoesNotExist:
                ts_status.append({
                    "employee": emp,
                    "timesheet": None,
                    "status": "MISSING",
                    "hours": 0,
                })

    # Expense status for selected month
    expense_status = []
    if selected_expense_month:
        for emp in active_employees:
            try:
                er = ExpenseReport.objects.get(employee=emp, month=selected_expense_month)
                expense_status.append({
                    "employee": emp,
                    "report": er,
                    "status": er.status,
                    "total": er.grand_total,
                })
            except ExpenseReport.DoesNotExist:
                expense_status.append({
                    "employee": emp,
                    "report": None,
                    "status": "MISSING",
                    "total": 0,
                })

    # Pending reviews count
    pending_timesheets = Timesheet.objects.filter(status=Timesheet.Status.SUBMITTED).count()
    pending_expenses = ExpenseReport.objects.filter(status=ExpenseReport.Status.SUBMITTED).count()

    context = {
        "current_ts_period": current_ts_period,
        "current_expense_month": current_expense_month,
        "selected_ts_period": selected_ts_period,
        "selected_expense_month": selected_expense_month,
        "recent_ts_periods": recent_ts_periods,
        "recent_expense_months": recent_expense_months,
        "ts_status": ts_status,
        "expense_status": expense_status,
        "pending_timesheets": pending_timesheets,
        "pending_expenses": pending_expenses,
    }
    return render(request, "reviews/dashboard.html", context)


@login_required
@office_manager_required
def pending_reviews(request):
    """List all pending submissions awaiting review."""
    pending_timesheets = Timesheet.objects.filter(
        status=Timesheet.Status.SUBMITTED
    ).select_related("employee", "period").order_by("submitted_at")

    pending_expenses = ExpenseReport.objects.filter(
        status=ExpenseReport.Status.SUBMITTED
    ).select_related("employee", "month").order_by("submitted_at")

    context = {
        "pending_timesheets": pending_timesheets,
        "pending_expenses": pending_expenses,
    }
    return render(request, "reviews/pending.html", context)


@login_required
@office_manager_required
def review_timesheet(request, pk):
    """Review a submitted timesheet."""
    timesheet = get_object_or_404(
        Timesheet.objects.select_related("employee", "period", "employee__profile"),
        pk=pk,
    )

    lines = timesheet.lines.select_related("charge_code").prefetch_related("entries").all()

    # Get date range
    from apps.timesheets.views import _get_period_dates
    dates = _get_period_dates(timesheet.period)

    # Build entry data
    entry_data = {}
    for line in lines:
        entry_data[line.id] = {entry.date: entry.hours for entry in line.entries.all()}

    # Get review history
    ct = ContentType.objects.get_for_model(Timesheet)
    actions = ReviewAction.objects.filter(
        content_type=ct, object_id=timesheet.pk
    ).select_related("actor").order_by("-created_at")

    comments = ReviewComment.objects.filter(
        content_type=ct, object_id=timesheet.pk
    ).select_related("author").order_by("created_at")

    context = {
        "timesheet": timesheet,
        "lines": lines,
        "dates": dates,
        "entry_data": entry_data,
        "actions": actions,
        "comments": comments,
    }
    return render(request, "reviews/review_timesheet.html", context)


@login_required
@office_manager_required
@require_POST
def approve_timesheet(request, pk):
    """Approve a submitted timesheet."""
    timesheet = get_object_or_404(Timesheet, pk=pk)

    if timesheet.status != Timesheet.Status.SUBMITTED:
        messages.error(request, "Only submitted timesheets can be approved.")
        return redirect("reviews:review_timesheet", pk=pk)

    try:
        with transaction.atomic():
            timesheet.approve(request.user)
            ReviewAction.log_action(
                timesheet,
                ReviewAction.ActionType.APPROVED,
                request.user,
                request.POST.get("comment", "")
            )
        messages.success(request, f"Timesheet for {timesheet.employee.get_full_name()} approved.")
    except Exception as e:
        messages.error(request, str(e))

    # Redirect to next pending or dashboard
    next_pending = Timesheet.objects.filter(status=Timesheet.Status.SUBMITTED).first()
    if next_pending:
        return redirect("reviews:review_timesheet", pk=next_pending.pk)
    return redirect("reviews:dashboard")


@login_required
@office_manager_required
@require_POST
def return_timesheet(request, pk):
    """Return a timesheet for revision."""
    timesheet = get_object_or_404(Timesheet, pk=pk)

    if timesheet.status != Timesheet.Status.SUBMITTED:
        messages.error(request, "Only submitted timesheets can be returned.")
        return redirect("reviews:review_timesheet", pk=pk)

    comment = request.POST.get("comment", "").strip()
    if not comment:
        messages.error(request, "Please provide a reason for returning the timesheet.")
        return redirect("reviews:review_timesheet", pk=pk)

    try:
        with transaction.atomic():
            timesheet.return_for_revision(comment)
            ReviewAction.log_action(
                timesheet,
                ReviewAction.ActionType.RETURNED,
                request.user,
                comment
            )
        messages.success(request, f"Timesheet returned to {timesheet.employee.get_full_name()}.")
    except Exception as e:
        messages.error(request, str(e))

    return redirect("reviews:pending")


@login_required
@office_manager_required
def review_expense(request, pk):
    """Review a submitted expense report."""
    report = get_object_or_404(
        ExpenseReport.objects.select_related("employee", "month", "employee__profile"),
        pk=pk,
    )

    items = report.items.select_related("category").prefetch_related("receipts").order_by("date")
    mileage_entries = report.mileage_entries.order_by("date")

    # Get review history
    ct = ContentType.objects.get_for_model(ExpenseReport)
    actions = ReviewAction.objects.filter(
        content_type=ct, object_id=report.pk
    ).select_related("actor").order_by("-created_at")

    comments = ReviewComment.objects.filter(
        content_type=ct, object_id=report.pk
    ).select_related("author").order_by("created_at")

    context = {
        "report": report,
        "items": items,
        "mileage_entries": mileage_entries,
        "actions": actions,
        "comments": comments,
    }
    return render(request, "reviews/review_expense.html", context)


@login_required
@office_manager_required
@require_POST
def approve_expense(request, pk):
    """Approve a submitted expense report."""
    report = get_object_or_404(ExpenseReport, pk=pk)

    if report.status != ExpenseReport.Status.SUBMITTED:
        messages.error(request, "Only submitted expense reports can be approved.")
        return redirect("reviews:review_expense", pk=pk)

    try:
        with transaction.atomic():
            report.approve(request.user)
            ReviewAction.log_action(
                report,
                ReviewAction.ActionType.APPROVED,
                request.user,
                request.POST.get("comment", "")
            )
        messages.success(request, f"Expense report for {report.employee.get_full_name()} approved.")
    except Exception as e:
        messages.error(request, str(e))

    next_pending = ExpenseReport.objects.filter(status=ExpenseReport.Status.SUBMITTED).first()
    if next_pending:
        return redirect("reviews:review_expense", pk=next_pending.pk)
    return redirect("reviews:dashboard")


@login_required
@office_manager_required
@require_POST
def return_expense(request, pk):
    """Return an expense report for revision."""
    report = get_object_or_404(ExpenseReport, pk=pk)

    if report.status != ExpenseReport.Status.SUBMITTED:
        messages.error(request, "Only submitted expense reports can be returned.")
        return redirect("reviews:review_expense", pk=pk)

    comment = request.POST.get("comment", "").strip()
    if not comment:
        messages.error(request, "Please provide a reason for returning the expense report.")
        return redirect("reviews:review_expense", pk=pk)

    try:
        with transaction.atomic():
            report.return_for_revision(comment)
            ReviewAction.log_action(
                report,
                ReviewAction.ActionType.RETURNED,
                request.user,
                comment
            )
        messages.success(request, f"Expense report returned to {report.employee.get_full_name()}.")
    except Exception as e:
        messages.error(request, str(e))

    return redirect("reviews:pending")


@login_required
@office_manager_required
@require_POST
def add_comment(request, content_type, pk):
    """Add a comment to a timesheet or expense report."""
    if content_type == "timesheet":
        obj = get_object_or_404(Timesheet, pk=pk)
    elif content_type == "expense":
        obj = get_object_or_404(ExpenseReport, pk=pk)
    else:
        return HttpResponse("Invalid content type", status=400)

    text = request.POST.get("comment", "").strip()
    is_internal = request.POST.get("is_internal") == "on"

    if not text:
        return HttpResponse("Comment cannot be empty", status=400)

    ct = ContentType.objects.get_for_model(obj)
    ReviewComment.objects.create(
        content_type=ct,
        object_id=obj.pk,
        author=request.user,
        text=text,
        is_internal=is_internal,
    )

    if content_type == "timesheet":
        return redirect("reviews:review_timesheet", pk=pk)
    else:
        return redirect("reviews:review_expense", pk=pk)


# =============================================================================
# MANAGING PARTNER VIEWS
# =============================================================================

def _get_period_dates(period):
    """Get list of dates for a timesheet period."""
    dates = []
    current = period.start_date
    while current <= period.end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _get_daily_hours(timesheet, dates):
    """Get hours by date for a timesheet."""
    daily = {d: Decimal("0") for d in dates}
    for line in timesheet.lines.prefetch_related("entries").all():
        for entry in line.entries.all():
            if entry.date in daily:
                daily[entry.date] += entry.hours
    return daily


def _check_flags(daily_hours):
    """
    Check for flags:
    - Incomplete days (less than 8 hours on weekdays)
    - More than 10 hours per day for more than 2 days in a week
    """
    flags = {
        "incomplete_days": [],
        "excessive_hours_weeks": [],
    }
    
    # Group by ISO week
    weeks = defaultdict(list)
    
    for date, hours in daily_hours.items():
        # Skip weekends
        if date.weekday() >= 5:
            continue
        
        # Check incomplete (less than 8 hours on weekday)
        if hours < 8:
            flags["incomplete_days"].append({
                "date": date,
                "hours": hours,
            })
        
        # Track days with >10 hours by week
        week_key = date.isocalendar()[:2]  # (year, week)
        if hours > 10:
            weeks[week_key].append(date)
    
    # Check if any week has more than 2 days with >10 hours
    for week_key, dates in weeks.items():
        if len(dates) > 2:
            flags["excessive_hours_weeks"].append({
                "week": week_key,
                "dates": dates,
                "count": len(dates),
            })
    
    return flags


@login_required
@managing_partner_required
def managing_partner_dashboard(request):
    """Managing Partner dashboard with period selection."""
    # Get recent periods
    recent_ts_periods = TimesheetPeriod.objects.order_by("-year", "-month", "-half")[:12]
    current_period = TimesheetPeriod.get_current_period()
    
    # Get selected period
    period_id = request.GET.get("period")
    if period_id:
        selected_period = TimesheetPeriod.objects.filter(pk=period_id).first()
    else:
        selected_period = current_period
    
    context = {
        "recent_periods": recent_ts_periods,
        "selected_period": selected_period,
        "current_period": current_period,
    }
    return render(request, "reviews/managing_partner/dashboard.html", context)


@login_required
@managing_partner_required
def daily_summary(request, period_id=None):
    """
    By-day timesheet summary for a half-month period.
    Shows hours by day for each employee with flags.
    """
    if period_id:
        period = get_object_or_404(TimesheetPeriod, pk=period_id)
    else:
        period = TimesheetPeriod.get_current_period()
        if not period:
            return render(request, "reviews/managing_partner/no_period.html")
    
    dates = _get_period_dates(period)
    
    # Get all employees with timesheets
    employees = User.objects.filter(
        is_active=True,
        groups__name="employees"
    ).select_related("profile").distinct().order_by("last_name", "first_name")
    
    employee_data = []
    for emp in employees:
        try:
            ts = Timesheet.objects.get(employee=emp, period=period)
            daily_hours = _get_daily_hours(ts, dates)
            flags = _check_flags(daily_hours)
            total = sum(daily_hours.values())
            
            employee_data.append({
                "employee": emp,
                "timesheet": ts,
                "daily_hours": daily_hours,
                "total_hours": total,
                "flags": flags,
                "has_flags": bool(flags["incomplete_days"] or flags["excessive_hours_weeks"]),
            })
        except Timesheet.DoesNotExist:
            # No timesheet for this period
            employee_data.append({
                "employee": emp,
                "timesheet": None,
                "daily_hours": {d: Decimal("0") for d in dates},
                "total_hours": Decimal("0"),
                "flags": {"incomplete_days": [], "excessive_hours_weeks": []},
                "has_flags": True,  # Missing timesheet is a flag
                "missing": True,
            })
    
    # Get recent periods for navigation
    recent_periods = TimesheetPeriod.objects.order_by("-year", "-month", "-half")[:12]
    
    context = {
        "period": period,
        "dates": dates,
        "employee_data": employee_data,
        "recent_periods": recent_periods,
    }
    return render(request, "reviews/managing_partner/daily_summary.html", context)


@login_required
@managing_partner_required
def category_summary(request, period_id=None):
    """
    Category summary for a half-month period.
    People horizontal, categories vertical.
    """
    if period_id:
        period = get_object_or_404(TimesheetPeriod, pk=period_id)
    else:
        period = TimesheetPeriod.get_current_period()
        if not period:
            return render(request, "reviews/managing_partner/no_period.html")
    
    # Get all employees
    employees = User.objects.filter(
        is_active=True,
        groups__name="employees"
    ).select_related("profile").distinct().order_by("last_name", "first_name")
    
    # Get all charge codes, clients first, then others
    charge_codes = list(ChargeCode.objects.filter(active=True).order_by("-is_client_work", "code"))
    
    # Build the summary grid
    # Structure: {charge_code_id: {employee_id: hours}}
    summary = defaultdict(lambda: defaultdict(Decimal))
    employee_totals = defaultdict(Decimal)
    code_totals = defaultdict(Decimal)
    
    for emp in employees:
        try:
            ts = Timesheet.objects.get(employee=emp, period=period)
            for line in ts.lines.select_related("charge_code").prefetch_related("entries").all():
                total_hours = sum(e.hours for e in line.entries.all())
                # Use code + label for client work
                key = f"{line.charge_code_id}:{line.label}" if line.label else str(line.charge_code_id)
                summary[key][emp.id] = total_hours
                employee_totals[emp.id] += total_hours
                code_totals[key] += total_hours
        except Timesheet.DoesNotExist:
            pass
    
    # Build ordered list of category rows
    category_rows = []
    
    # First, client work (sorted by total hours descending)
    client_keys = [k for k in summary.keys() if ":" in k]
    client_keys.sort(key=lambda k: code_totals[k], reverse=True)
    
    for key in client_keys:
        code_id, label = key.split(":", 1)
        try:
            code = ChargeCode.objects.get(pk=int(code_id))
            category_rows.append({
                "key": key,
                "name": f"{code.code}: {label}",
                "is_client": True,
                "hours_by_employee": summary[key],
                "total": code_totals[key],
            })
        except ChargeCode.DoesNotExist:
            pass
    
    # Then, other charge codes (sorted by code)
    other_keys = [k for k in summary.keys() if ":" not in k]
    for key in sorted(other_keys, key=lambda k: ChargeCode.objects.get(pk=int(k)).code if k.isdigit() else k):
        try:
            code = ChargeCode.objects.get(pk=int(key))
            category_rows.append({
                "key": key,
                "name": f"{code.code} - {code.description}",
                "is_client": False,
                "hours_by_employee": summary[key],
                "total": code_totals[key],
            })
        except (ChargeCode.DoesNotExist, ValueError):
            pass
    
    # Get recent periods for navigation
    recent_periods = TimesheetPeriod.objects.order_by("-year", "-month", "-half")[:12]
    
    context = {
        "period": period,
        "employees": employees,
        "category_rows": category_rows,
        "employee_totals": employee_totals,
        "recent_periods": recent_periods,
    }
    return render(request, "reviews/managing_partner/category_summary.html", context)


# =============================================================================
# PAYROLL PARTNER VIEWS
# =============================================================================

@login_required
@payroll_partner_required
def payroll_dashboard(request):
    """Payroll Partner dashboard."""
    # Get recent expense months
    recent_months = ExpenseMonth.objects.order_by("-year", "-month")[:6]
    current_month = ExpenseMonth.get_current_month()
    
    # Get selected month
    month_id = request.GET.get("month")
    if month_id:
        selected_month = ExpenseMonth.objects.filter(pk=month_id).first()
    else:
        selected_month = current_month
    
    # Get expense summary for selected month
    expense_summary = []
    if selected_month:
        employees = User.objects.filter(
            is_active=True,
            groups__name="employees"
        ).select_related("profile").distinct().order_by("last_name", "first_name")
        
        for emp in employees:
            try:
                report = ExpenseReport.objects.get(employee=emp, month=selected_month)
                expense_summary.append({
                    "employee": emp,
                    "report": report,
                    "total": report.grand_total,
                    "status": report.status,
                })
            except ExpenseReport.DoesNotExist:
                expense_summary.append({
                    "employee": emp,
                    "report": None,
                    "total": Decimal("0"),
                    "status": "MISSING",
                })
    
    context = {
        "recent_months": recent_months,
        "selected_month": selected_month,
        "current_month": current_month,
        "expense_summary": expense_summary,
    }
    return render(request, "reviews/payroll/dashboard.html", context)


@login_required
@payroll_partner_required
def payroll_export(request, month_id):
    """
    Export expense data for payroll processing.
    Generates Excel/CSV with columns D through AS for expenses by person.
    """
    month = get_object_or_404(ExpenseMonth, pk=month_id)
    
    # Get all employees
    employees = list(User.objects.filter(
        is_active=True,
        groups__name="employees"
    ).select_related("profile").distinct().order_by("last_name", "first_name"))
    
    # Get all expense categories (ordered)
    categories = list(ExpenseCategory.objects.filter(active=True).order_by("name"))
    
    # Build data: rows are categories, columns are employees
    # Plus mileage as the last category
    
    format_type = request.GET.get("format", "xlsx")
    
    if format_type == "csv":
        return _payroll_export_csv(month, employees, categories)
    else:
        return _payroll_export_xlsx(month, employees, categories)


def _payroll_export_xlsx(month, employees, categories):
    """Generate Excel export for payroll."""
    if not HAS_OPENPYXL:
        return HttpResponse("openpyxl not installed", status=500)
    
    wb = Workbook()
    ws = wb.active
    ws.title = f"Expenses {month.display_name}"
    
    # Styles
    header_font = Font(bold=True, size=11)
    header_fill = PatternFill(start_color="1a1a2e", end_color="1a1a2e", fill_type="solid")
    header_font_white = Font(bold=True, size=11, color="FFFFFF")
    money_format = '"$"#,##0.00'
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Header row
    ws.cell(row=1, column=1, value="Category").font = header_font
    ws.cell(row=1, column=1).fill = header_fill
    ws.cell(row=1, column=1).font = header_font_white
    
    for col_idx, emp in enumerate(employees, start=2):
        cell = ws.cell(row=1, column=col_idx)
        cell.value = emp.get_full_name() or emp.email
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = 15
    
    # Total column
    total_col = len(employees) + 2
    ws.cell(row=1, column=total_col, value="Total").font = header_font_white
    ws.cell(row=1, column=total_col).fill = header_fill
    
    # Data rows - expense categories
    current_row = 2
    for cat in categories:
        ws.cell(row=current_row, column=1, value=cat.name)
        row_total = Decimal("0")
        
        for col_idx, emp in enumerate(employees, start=2):
            try:
                report = ExpenseReport.objects.get(employee=emp, month=month)
                cat_total = report.items.filter(category=cat).aggregate(
                    total=Sum("amount")
                )["total"] or Decimal("0")
            except ExpenseReport.DoesNotExist:
                cat_total = Decimal("0")
            
            cell = ws.cell(row=current_row, column=col_idx, value=float(cat_total))
            cell.number_format = money_format
            cell.border = thin_border
            row_total += cat_total
        
        # Row total
        ws.cell(row=current_row, column=total_col, value=float(row_total)).number_format = money_format
        current_row += 1
    
    # Mileage row
    ws.cell(row=current_row, column=1, value="Mileage Reimbursement")
    mileage_total = Decimal("0")
    
    for col_idx, emp in enumerate(employees, start=2):
        try:
            report = ExpenseReport.objects.get(employee=emp, month=month)
            emp_mileage = report.total_mileage_amount
        except ExpenseReport.DoesNotExist:
            emp_mileage = Decimal("0")
        
        cell = ws.cell(row=current_row, column=col_idx, value=float(emp_mileage))
        cell.number_format = money_format
        cell.border = thin_border
        mileage_total += emp_mileage
    
    ws.cell(row=current_row, column=total_col, value=float(mileage_total)).number_format = money_format
    current_row += 1
    
    # Grand total row
    ws.cell(row=current_row, column=1, value="GRAND TOTAL").font = header_font
    
    for col_idx, emp in enumerate(employees, start=2):
        try:
            report = ExpenseReport.objects.get(employee=emp, month=month)
            emp_total = report.grand_total
        except ExpenseReport.DoesNotExist:
            emp_total = Decimal("0")
        
        cell = ws.cell(row=current_row, column=col_idx, value=float(emp_total))
        cell.number_format = money_format
        cell.font = header_font
        cell.border = thin_border
    
    # Set column width for first column
    ws.column_dimensions["A"].width = 25
    
    # Prepare response
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"payroll_expenses_{month.year}_{month.month:02d}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _payroll_export_csv(month, employees, categories):
    """Generate CSV export for payroll."""
    response = HttpResponse(content_type="text/csv")
    filename = f"payroll_expenses_{month.year}_{month.month:02d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Header row
    header = ["Category"] + [emp.get_full_name() or emp.email for emp in employees] + ["Total"]
    writer.writerow(header)
    
    # Data rows - expense categories
    for cat in categories:
        row = [cat.name]
        row_total = Decimal("0")
        
        for emp in employees:
            try:
                report = ExpenseReport.objects.get(employee=emp, month=month)
                cat_total = report.items.filter(category=cat).aggregate(
                    total=Sum("amount")
                )["total"] or Decimal("0")
            except ExpenseReport.DoesNotExist:
                cat_total = Decimal("0")
            
            row.append(f"{cat_total:.2f}")
            row_total += cat_total
        
        row.append(f"{row_total:.2f}")
        writer.writerow(row)
    
    # Mileage row
    mileage_row = ["Mileage Reimbursement"]
    mileage_total = Decimal("0")
    
    for emp in employees:
        try:
            report = ExpenseReport.objects.get(employee=emp, month=month)
            emp_mileage = report.total_mileage_amount
        except ExpenseReport.DoesNotExist:
            emp_mileage = Decimal("0")
        
        mileage_row.append(f"{emp_mileage:.2f}")
        mileage_total += emp_mileage
    
    mileage_row.append(f"{mileage_total:.2f}")
    writer.writerow(mileage_row)
    
    # Grand total row
    total_row = ["GRAND TOTAL"]
    grand_total = Decimal("0")
    
    for emp in employees:
        try:
            report = ExpenseReport.objects.get(employee=emp, month=month)
            emp_total = report.grand_total
        except ExpenseReport.DoesNotExist:
            emp_total = Decimal("0")
        
        total_row.append(f"{emp_total:.2f}")
        grand_total += emp_total
    
    total_row.append(f"{grand_total:.2f}")
    writer.writerow(total_row)
    
    return response
