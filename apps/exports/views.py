"""
Export generation views for timesheets and expense reports.
"""
import os
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden, FileResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings

from apps.periods.models import TimesheetPeriod, ExpenseMonth
from apps.timesheets.models import Timesheet
from apps.expenses.models import ExpenseReport
from .models import ExportJob, ExportDownload
from .services import (
    generate_timesheet_xlsx,
    generate_expense_xlsx,
    convert_xlsx_to_pdf,
    merge_pdfs,
    create_zip_bundle,
)


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
    # Get recent periods
    recent_ts_periods = TimesheetPeriod.objects.order_by("-year", "-month", "-half")[:12]
    recent_expense_months = ExpenseMonth.objects.order_by("-year", "-month")[:6]

    # Recent export jobs
    recent_exports = ExportJob.objects.order_by("-created_at")[:20]

    context = {
        "recent_ts_periods": recent_ts_periods,
        "recent_expense_months": recent_expense_months,
        "recent_exports": recent_exports,
    }
    return render(request, "exports/dashboard.html", context)


@login_required
@office_manager_required
@require_POST
def generate_timesheet_exports(request):
    """Generate timesheet exports for a period."""
    period_id = request.POST.get("period_id")
    period = get_object_or_404(TimesheetPeriod, pk=period_id)

    export_type = request.POST.get("export_type", "xlsx")  # xlsx, pdf, pack, all

    # Get all approved timesheets for this period
    timesheets = Timesheet.objects.filter(
        period=period,
        status=Timesheet.Status.APPROVED
    ).select_related("employee", "employee__profile").order_by(
        "employee__profile__seniority_order", "employee__last_name"
    )

    if not timesheets.exists():
        messages.warning(request, "No approved timesheets found for this period.")
        return redirect("exports:dashboard")

    generated_files = []
    errors = []

    for ts in timesheets:
        try:
            xlsx_path = generate_timesheet_xlsx(ts)
            generated_files.append(xlsx_path)

            # Create export job record
            ExportJob.objects.create(
                export_type=ExportJob.ExportType.TIMESHEET_XLSX,
                status=ExportJob.Status.COMPLETED,
                year=period.year,
                month=period.month,
                half=period.half,
                employee=ts.employee,
                filename=os.path.basename(xlsx_path),
                created_by=request.user,
                completed_at=timezone.now(),
            )

            if export_type in ("pdf", "pack", "all"):
                pdf_path = convert_xlsx_to_pdf(xlsx_path)
                generated_files.append(pdf_path)

        except Exception as e:
            errors.append(f"{ts.employee.get_full_name()}: {str(e)}")

    # Create PDF pack if requested
    if export_type in ("pack", "all") and generated_files:
        try:
            pdf_files = [f for f in generated_files if str(f).endswith(".pdf")]
            if pdf_files:
                pack_path = os.path.join(
                    settings.EXPORT_ROOT,
                    f"timesheets_{period.year}_{period.month:02d}_{period.half}_pack.pdf"
                )
                merge_pdfs(pdf_files, pack_path)

                ExportJob.objects.create(
                    export_type=ExportJob.ExportType.TIMESHEET_PACK,
                    status=ExportJob.Status.COMPLETED,
                    year=period.year,
                    month=period.month,
                    half=period.half,
                    filename=os.path.basename(pack_path),
                    created_by=request.user,
                    completed_at=timezone.now(),
                )
        except Exception as e:
            errors.append(f"PDF Pack: {str(e)}")

    if errors:
        messages.warning(request, f"Exports completed with {len(errors)} error(s): {'; '.join(errors[:3])}")
    else:
        messages.success(request, f"Generated {len(generated_files)} export files.")

    return redirect("exports:dashboard")


@login_required
@office_manager_required
@require_POST
def generate_expense_exports(request):
    """Generate expense exports for a month."""
    month_id = request.POST.get("month_id")
    month = get_object_or_404(ExpenseMonth, pk=month_id)

    export_type = request.POST.get("export_type", "xlsx")
    sort_by = request.POST.get("sort_by", "seniority")  # seniority or alpha

    # Get all approved expense reports
    reports = ExpenseReport.objects.filter(
        month=month,
        status=ExpenseReport.Status.APPROVED
    ).select_related("employee", "employee__profile")

    if sort_by == "alpha":
        reports = reports.order_by("employee__last_name", "employee__first_name")
    else:
        reports = reports.order_by("employee__profile__seniority_order", "employee__last_name")

    if not reports.exists():
        messages.warning(request, "No approved expense reports found for this month.")
        return redirect("exports:dashboard")

    generated_files = []
    errors = []

    for report in reports:
        try:
            xlsx_path = generate_expense_xlsx(report)
            generated_files.append(xlsx_path)

            ExportJob.objects.create(
                export_type=ExportJob.ExportType.EXPENSE_XLSX,
                status=ExportJob.Status.COMPLETED,
                year=month.year,
                month=month.month,
                employee=report.employee,
                filename=os.path.basename(xlsx_path),
                created_by=request.user,
                completed_at=timezone.now(),
            )

            if export_type in ("pdf", "pack", "all"):
                pdf_path = convert_xlsx_to_pdf(xlsx_path)
                generated_files.append(pdf_path)

        except Exception as e:
            errors.append(f"{report.employee.get_full_name()}: {str(e)}")

    if errors:
        messages.warning(request, f"Exports completed with {len(errors)} error(s)")
    else:
        messages.success(request, f"Generated {len(generated_files)} export files.")

    return redirect("exports:dashboard")


@login_required
@office_manager_required
def download_export(request, pk):
    """Download an export file and log the download."""
    export = get_object_or_404(ExportJob, pk=pk)

    if not export.file:
        messages.error(request, "Export file not found.")
        return redirect("exports:dashboard")

    # Log the download
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

    # Filtering
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
