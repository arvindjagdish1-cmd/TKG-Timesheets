"""
Export generation views for timesheets and expense reports.
"""
import os
import logging
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, FileResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.timesheets.models import TimesheetUpload
from apps.periods.models import ExpenseMonth
from apps.expenses.models import ExpenseReport
from .models import ExportJob, ExportDownload
from .services import (
    generate_upload_xlsx,
    generate_expense_xlsx,
)

logger = logging.getLogger(__name__)


def office_manager_required(view_func):
    """Decorator to require office_manager or higher role."""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")
        allowed_groups = ["office_manager", "managing_partner", "payroll_partner", "accountants"]
        if not request.user.groups.filter(name__in=allowed_groups).exists() and not request.user.is_superuser:
            return HttpResponseForbidden("Access denied.")
        return view_func(request, *args, **kwargs)
    return wrapped


@login_required
@office_manager_required
def export_dashboard(request):
    """Export generation dashboard."""
    ts_months = (
        TimesheetUpload.objects
        .values_list("year", "month")
        .distinct()
        .order_by("-year", "-month")
    )
    expense_months = ExpenseMonth.objects.order_by("-year", "-month")
    recent_exports = ExportJob.objects.order_by("-created_at")[:20]

    context = {
        "ts_months": ts_months,
        "expense_months": expense_months,
        "recent_exports": recent_exports,
    }
    return render(request, "exports/dashboard.html", context)


@login_required
@office_manager_required
@require_POST
def generate_timesheet_exports(request):
    """Generate timesheet exports from TimesheetUpload data."""
    year = request.POST.get("year")
    month = request.POST.get("month")

    if not year or not month:
        messages.warning(request, "Please select a month to export.")
        return redirect("exports:export_dashboard")

    try:
        year, month = int(year), int(month)
    except (ValueError, TypeError):
        messages.warning(request, "Invalid month selection.")
        return redirect("exports:export_dashboard")

    uploads = TimesheetUpload.objects.filter(
        year=year,
        month=month,
    ).exclude(
        status=TimesheetUpload.Status.DRAFT,
    ).select_related("user").order_by(
        "user__last_name", "user__first_name"
    )

    if not uploads.exists():
        messages.warning(
            request,
            f"No submitted timesheets found for {year}-{month:02d}. "
            "Timesheets must be submitted before they can be exported."
        )
        return redirect("exports:export_dashboard")

    generated = []
    errors = []

    for upload in uploads:
        try:
            xlsx_path = generate_upload_xlsx(upload)
            generated.append(xlsx_path)

            ExportJob.objects.create(
                export_type=ExportJob.ExportType.TIMESHEET_XLSX,
                status=ExportJob.Status.COMPLETED,
                year=year,
                month=month,
                half="",
                employee=upload.user,
                filename=os.path.basename(str(xlsx_path)),
                created_by=request.user,
                completed_at=timezone.now(),
            )
        except Exception as e:
            logger.exception("Export failed for %s", upload)
            errors.append(f"{upload.user.get_full_name()}: {str(e)}")

    if errors:
        messages.warning(
            request,
            f"Generated {len(generated)} file(s) with {len(errors)} error(s): "
            f"{'; '.join(errors[:3])}"
        )
    else:
        messages.success(request, f"Generated {len(generated)} timesheet export(s).")

    return redirect("exports:export_dashboard")


@login_required
@office_manager_required
@require_POST
def generate_expense_exports(request):
    """Generate expense exports for a month."""
    year = request.POST.get("year")
    month = request.POST.get("month")

    if not year or not month:
        messages.warning(request, "Please select a month to export.")
        return redirect("exports:export_dashboard")

    try:
        year, month = int(year), int(month)
    except (ValueError, TypeError):
        messages.warning(request, "Invalid month selection.")
        return redirect("exports:export_dashboard")

    expense_month = ExpenseMonth.objects.filter(year=year, month=month).first()
    if not expense_month:
        messages.warning(
            request,
            f"No expense period found for {year}-{month:02d}. "
            "An expense period must be created in the admin before reports can be exported."
        )
        return redirect("exports:export_dashboard")

    reports = ExpenseReport.objects.filter(
        month=expense_month,
    ).exclude(
        status=ExpenseReport.Status.DRAFT,
    ).select_related("employee").order_by(
        "employee__last_name", "employee__first_name"
    )

    if not reports.exists():
        messages.warning(
            request,
            f"No submitted expense reports found for {year}-{month:02d}."
        )
        return redirect("exports:export_dashboard")

    generated = []
    errors = []

    for report in reports:
        try:
            xlsx_path = generate_expense_xlsx(report)
            generated.append(xlsx_path)

            ExportJob.objects.create(
                export_type=ExportJob.ExportType.EXPENSE_XLSX,
                status=ExportJob.Status.COMPLETED,
                year=year,
                month=month,
                employee=report.employee,
                filename=os.path.basename(str(xlsx_path)),
                created_by=request.user,
                completed_at=timezone.now(),
            )
        except Exception as e:
            logger.exception("Expense export failed for %s", report)
            errors.append(f"{report.employee.get_full_name()}: {str(e)}")

    if errors:
        messages.warning(
            request,
            f"Generated {len(generated)} file(s) with {len(errors)} error(s): "
            f"{'; '.join(errors[:3])}"
        )
    else:
        messages.success(request, f"Generated {len(generated)} expense export(s).")

    return redirect("exports:export_dashboard")


@login_required
@office_manager_required
def download_export(request, pk):
    """Download an export file and log the download."""
    export = get_object_or_404(ExportJob, pk=pk)

    if not export.file:
        messages.error(request, "Export file not found.")
        return redirect("exports:export_dashboard")

    ExportDownload.objects.create(
        export=export,
        downloaded_by=request.user,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )

    return FileResponse(
        export.file.open("rb"),
        as_attachment=True,
        filename=export.filename or export.file.name,
    )


@login_required
@office_manager_required
def export_list(request):
    """List all exports with filtering."""
    exports = ExportJob.objects.order_by("-created_at")

    year = request.GET.get("year")
    month = request.GET.get("month")
    export_type = request.GET.get("type")

    if year:
        exports = exports.filter(year=year)
    if month:
        exports = exports.filter(month=month)
    if export_type:
        exports = exports.filter(export_type=export_type)

    exports = exports[:100]

    context = {
        "exports": exports,
        "years": range(datetime.now().year, datetime.now().year - 3, -1),
        "export_types": ExportJob.ExportType.choices,
    }
    return render(request, "exports/list.html", context)
