"""
Office Manager review dashboard and approval workflow.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from apps.timesheets.models import Timesheet
from apps.expenses.models import ExpenseReport
from apps.periods.models import TimesheetPeriod, ExpenseMonth
from apps.accounts.models import User, EmployeeProfile
from .models import ReviewAction, ReviewComment


def office_manager_required(view_func):
    """Decorator to require office_manager or higher role."""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        if not request.user.groups.filter(
            name__in=["office_manager", "managing_partner"]
        ).exists() and not request.user.is_superuser:
            return HttpResponseForbidden("Access denied. Office Manager role required.")
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
