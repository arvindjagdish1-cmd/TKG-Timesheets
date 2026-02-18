from datetime import timedelta
from decimal import Decimal, InvalidOperation
import json

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse, FileResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.template.loader import render_to_string

from .models import Timesheet, TimesheetLine, TimeEntry, ChargeCode, TimesheetUpload
from apps.periods.models import TimesheetPeriod, ExpenseMonth
from apps.expenses.models import ExpenseReport
from apps.reviews.models import ReviewAction
from .services.upload_parser import parse_timesheet_workbook
from .services.upload_validation import validate_parsed_workbook


@login_required
def dashboard(request):
    """Main dashboard showing the employee's current periods and status."""
    user = request.user
    today = timezone.now().date()
    current_year = today.year
    current_month = today.month

    # Get current periods
    current_ts_period = TimesheetPeriod.get_current_period()
    current_expense_month = ExpenseMonth.get_current_month()

    latest_upload = TimesheetUpload.objects.filter(
        user=user,
        year=current_year,
        month=current_month,
    ).order_by("-uploaded_at").first()

    recent_uploads = TimesheetUpload.objects.filter(
        user=user,
    ).order_by("-uploaded_at")[:6]

    # Get user's expense reports (current and recent)
    expense_reports = ExpenseReport.objects.filter(employee=user).select_related("month").order_by(
        "-month__year", "-month__month"
    )[:3]

    # Get or create current timesheet if period exists
    current_timesheet = None
    if current_ts_period:
        current_timesheet, _ = Timesheet.objects.get_or_create(
            employee=user,
            period=current_ts_period,
        )

    # Get or create current expense report if month exists
    current_expense = None
    if current_expense_month:
        current_expense, _ = ExpenseReport.objects.get_or_create(
            employee=user,
            month=current_expense_month,
        )

    context = {
        "current_timesheet": current_timesheet,
        "current_expense": current_expense,
        "recent_uploads": recent_uploads,
        "expense_reports": expense_reports,
        "current_ts_period": current_ts_period,
        "current_expense_month": current_expense_month,
        "today": today,
        "latest_upload": latest_upload,
    }
    return render(request, "timesheets/dashboard.html", context)


@login_required
def upload_timesheet(request):
    """Upload-first workflow for timesheets and expenses."""
    user = request.user
    today = timezone.now().date()
    latest_upload = TimesheetUpload.objects.filter(
        user=user, year=today.year, month=today.month
    ).order_by("-uploaded_at").first()

    if request.method == "POST":
        upload_file = request.FILES.get("timesheet_file")
        if not upload_file:
            messages.error(request, "Please select a file to upload.")
            return redirect("timesheets:upload_timesheet")

        if not upload_file.name.lower().endswith(".xlsx"):
            messages.error(request, "Only .xlsx files are accepted.")
            return redirect("timesheets:upload_timesheet")

        max_mb = getattr(settings, "TIMESHEET_UPLOAD_MAX_MB", 25)
        if upload_file.size > max_mb * 1024 * 1024:
            messages.error(request, f"File exceeds the {max_mb} MB limit.")
            return redirect("timesheets:upload_timesheet")

        file_bytes = upload_file.read()
        parsed = parse_timesheet_workbook(file_bytes)
        issues = validate_parsed_workbook(parsed)
        has_blocking = any(issue["severity"] == "ERROR" for issue in issues)

        year = parsed.get("period", {}).get("year") or today.year
        month = parsed.get("period", {}).get("month") or today.month
        template_version = parsed.get("metadata", {}).get("template_version") or ""

        upload_file.seek(0)
        upload = TimesheetUpload.objects.create(
            user=user,
            uploaded_file=upload_file,
            year=year,
            month=month,
            status=TimesheetUpload.Status.DRAFT,
            parsed_json=parsed,
            errors_json=issues,
            has_blocking_errors=has_blocking,
            source_template_version=template_version,
        )
        upload.set_sha256_from_bytes(file_bytes)
        upload.save(update_fields=["sha256"])

        return redirect("timesheets:upload_summary", pk=upload.pk)

    context = {
        "latest_upload": latest_upload,
        "today": today,
        "TIMESHEET_UPLOAD_MAX_MB": getattr(settings, "TIMESHEET_UPLOAD_MAX_MB", 25),
    }
    return render(request, "timesheets/upload.html", context)


@login_required
def upload_list(request):
    """List all of the current user's timesheet uploads starting from Jan 2026."""
    uploads = (
        TimesheetUpload.objects.filter(user=request.user, year__gte=2026)
        .order_by("-year", "-month", "-uploaded_at")
    )

    rows = []
    seen = set()
    for u in uploads:
        key = (u.year, u.month)
        if key in seen:
            continue
        seen.add(key)
        summary = u.parsed_json or {}
        fh_hours = summary.get("time", {}).get("first_half", {}).get("total_hours", 0)
        sh_hours = summary.get("time", {}).get("second_half", {}).get("total_hours", 0)
        total_expenses = summary.get("expenses", {}).get("total_expenses", 0)
        rows.append({
            "upload": u,
            "first_half_hours": fh_hours,
            "second_half_hours": sh_hours,
            "total_expenses": total_expenses,
        })

    return render(request, "timesheets/upload_list.html", {"rows": rows})


@login_required
def upload_summary(request, pk):
    upload = get_object_or_404(TimesheetUpload, pk=pk)
    if upload.user != request.user and not request.user.groups.filter(
        name__in=["office_manager", "managing_partner", "payroll_partner", "accountants"]
    ).exists() and not request.user.is_superuser:
        return HttpResponseForbidden("You don't have permission to view this upload.")

    errors = [i for i in upload.errors_json if i.get("severity") == "ERROR"]
    warnings = [i for i in upload.errors_json if i.get("severity") == "WARN"]
    summary = upload.parsed_json or {}

    context = {
        "upload": upload,
        "summary": summary,
        "errors": errors,
        "warnings": warnings,
    }
    return render(request, "timesheets/summary.html", context)


@login_required
@require_POST
def upload_submit(request, pk):
    upload = get_object_or_404(TimesheetUpload, pk=pk, user=request.user)
    if upload.has_blocking_errors:
        messages.error(request, "Fix all blocking issues before submitting.")
        return redirect("timesheets:upload_summary", pk=pk)

    if upload.status != TimesheetUpload.Status.DRAFT:
        messages.error(request, "Only drafts can be submitted.")
        return redirect("timesheets:upload_summary", pk=pk)

    upload.status = TimesheetUpload.Status.SUBMITTED
    upload.save(update_fields=["status", "updated_at"])
    messages.success(request, "Upload submitted successfully.")
    return redirect("timesheets:upload_summary", pk=pk)


@login_required
def upload_download(request, pk):
    upload = get_object_or_404(TimesheetUpload, pk=pk)
    if upload.user != request.user and not request.user.groups.filter(
        name__in=["office_manager", "managing_partner", "payroll_partner"]
    ).exists() and not request.user.is_superuser:
        return HttpResponseForbidden("Access denied.")
    return FileResponse(upload.uploaded_file.open("rb"), as_attachment=True)


@login_required
def timesheet_list(request):
    """List all timesheets for the current user."""
    user = request.user
    timesheets = Timesheet.objects.filter(employee=user).select_related("period").order_by(
        "-period__year", "-period__month", "-period__half"
    )

    context = {
        "timesheets": timesheets,
    }
    return render(request, "timesheets/timesheet_list.html", context)


@login_required
def timesheet_detail(request, pk):
    """View a specific timesheet."""
    timesheet = get_object_or_404(
        Timesheet.objects.select_related("period", "employee"),
        pk=pk,
    )

    # Check permissions
    if timesheet.employee != request.user:
        if not request.user.groups.filter(
            name__in=["office_manager", "managing_partner", "payroll_partner", "accountants"]
        ).exists():
            return HttpResponseForbidden("You don't have permission to view this timesheet.")

    # Get lines with entries
    lines = timesheet.lines.select_related("charge_code").prefetch_related("entries").all()

    # Generate date range for the period
    dates = _get_period_dates(timesheet.period)

    # Build a lookup for entries by line and date
    entry_data = {}
    for line in lines:
        entry_data[line.id] = {entry.date: entry.hours for entry in line.entries.all()}

    context = {
        "timesheet": timesheet,
        "lines": lines,
        "dates": dates,
        "entry_data": entry_data,
    }
    return render(request, "timesheets/timesheet_detail.html", context)


@login_required
def timesheet_edit(request, pk):
    """Edit a timesheet (grid editor with HTMX)."""
    timesheet = get_object_or_404(
        Timesheet.objects.select_related("period", "employee"),
        pk=pk,
    )

    # Check ownership
    if timesheet.employee != request.user:
        return HttpResponseForbidden("You can only edit your own timesheets.")

    # Check if editable
    if not timesheet.is_editable:
        messages.error(request, "This timesheet cannot be edited.")
        return redirect("timesheets:timesheet_detail", pk=pk)

    # Get lines with entries
    lines = timesheet.lines.select_related("charge_code").prefetch_related("entries").order_by("order", "id")

    # Generate date range for the period
    dates = _get_period_dates(timesheet.period)

    # Build a lookup for entries by line and date
    entry_data = {}
    for line in lines:
        entry_data[line.id] = {entry.date: entry.hours for entry in line.entries.all()}

    # Get available charge codes for adding new lines
    existing_codes = set(line.charge_code_id for line in lines)
    available_codes = ChargeCode.objects.filter(active=True).order_by("code")

    context = {
        "timesheet": timesheet,
        "lines": lines,
        "dates": dates,
        "entry_data": entry_data,
        "available_codes": available_codes,
        "period": timesheet.period,
    }
    return render(request, "timesheets/timesheet_edit.html", context)


@login_required
@require_POST
def timesheet_save_entry(request, pk):
    """HTMX endpoint: Save a single time entry."""
    timesheet = get_object_or_404(Timesheet, pk=pk, employee=request.user)

    if not timesheet.is_editable:
        return HttpResponse("Timesheet is not editable", status=400)

    line_id = request.POST.get("line_id")
    date_str = request.POST.get("date")
    hours_str = request.POST.get("hours", "0")

    try:
        from datetime import datetime
        entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        hours = Decimal(hours_str) if hours_str else Decimal("0")
    except (ValueError, InvalidOperation):
        return HttpResponse("Invalid data", status=400)

    # Validate hours
    if hours < 0 or hours > 24:
        return HttpResponse("Hours must be between 0 and 24", status=400)

    line = get_object_or_404(TimesheetLine, pk=line_id, timesheet=timesheet)

    # Create or update the entry
    if hours > 0:
        entry, created = TimeEntry.objects.update_or_create(
            line=line,
            date=entry_date,
            defaults={"hours": hours}
        )
    else:
        # Delete entry if hours is 0
        TimeEntry.objects.filter(line=line, date=entry_date).delete()

    # Return updated totals
    line_total = line.total_hours
    timesheet.refresh_from_db()

    # Calculate day total
    day_total = sum(
        e.hours for e in TimeEntry.objects.filter(
            line__timesheet=timesheet,
            date=entry_date
        )
    )

    return JsonResponse({
        "success": True,
        "line_total": str(line_total),
        "day_total": str(day_total),
        "grand_total": str(timesheet.total_hours),
    })


@login_required
@require_POST
def timesheet_add_line(request, pk):
    """HTMX endpoint: Add a new charge code line to the timesheet."""
    timesheet = get_object_or_404(Timesheet, pk=pk, employee=request.user)

    if not timesheet.is_editable:
        return HttpResponse("Timesheet is not editable", status=400)

    charge_code_id = request.POST.get("charge_code")
    label = request.POST.get("label", "").strip()

    charge_code = get_object_or_404(ChargeCode, pk=charge_code_id, active=True)

    # Check for duplicate
    if TimesheetLine.objects.filter(timesheet=timesheet, charge_code=charge_code, label=label).exists():
        return HttpResponse("This charge code/label combination already exists", status=400)

    # Get max order
    max_order = timesheet.lines.aggregate(max_order=models.Max("order"))["max_order"] or 0

    line = TimesheetLine.objects.create(
        timesheet=timesheet,
        charge_code=charge_code,
        label=label,
        order=max_order + 1,
    )

    # Return the new row HTML
    dates = _get_period_dates(timesheet.period)
    html = render_to_string("timesheets/partials/timesheet_row.html", {
        "line": line,
        "dates": dates,
        "entry_data": {},
        "timesheet": timesheet,
    }, request=request)

    return HttpResponse(html)


@login_required
@require_POST
def timesheet_delete_line(request, pk, line_id):
    """HTMX endpoint: Delete a charge code line from the timesheet."""
    timesheet = get_object_or_404(Timesheet, pk=pk, employee=request.user)

    if not timesheet.is_editable:
        return HttpResponse("Timesheet is not editable", status=400)

    line = get_object_or_404(TimesheetLine, pk=line_id, timesheet=timesheet)
    line.delete()

    return HttpResponse("")


@login_required
@require_POST
def timesheet_submit(request, pk):
    """Submit a timesheet for review."""
    timesheet = get_object_or_404(Timesheet, pk=pk)

    if timesheet.employee != request.user:
        return HttpResponseForbidden("You can only submit your own timesheets.")

    try:
        with transaction.atomic():
            timesheet.submit()
            ReviewAction.log_action(
                timesheet,
                ReviewAction.ActionType.SUBMITTED,
                request.user,
                request.POST.get("notes", "")
            )
        messages.success(request, "Timesheet submitted successfully!")
    except Exception as e:
        messages.error(request, str(e))

    return redirect("timesheets:timesheet_detail", pk=pk)


@login_required
@require_POST
def timesheet_save_notes(request, pk):
    """HTMX endpoint: Save employee notes."""
    timesheet = get_object_or_404(Timesheet, pk=pk, employee=request.user)

    if not timesheet.is_editable:
        return HttpResponse("Timesheet is not editable", status=400)

    notes = request.POST.get("employee_notes", "")
    timesheet.employee_notes = notes
    timesheet.save(update_fields=["employee_notes", "updated_at"])

    return HttpResponse('<span class="text-success"><i class="bi bi-check"></i> Saved</span>')


def _get_period_dates(period):
    """Generate list of dates for a period."""
    dates = []
    current = period.start_date
    while current <= period.end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


# Import models for aggregate
from django.db import models
