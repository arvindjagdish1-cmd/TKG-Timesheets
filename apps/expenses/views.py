from datetime import timedelta
from decimal import Decimal, InvalidOperation
import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.template.loader import render_to_string
from django.core.files.storage import default_storage

from .models import ExpenseReport, ExpenseItem, ExpenseReceipt, MileageEntry, ExpenseCategory
from apps.periods.models import ExpenseMonth
from apps.reviews.models import ReviewAction


@login_required
def expense_list(request):
    """List all expense reports for the current user."""
    user = request.user
    reports = ExpenseReport.objects.filter(employee=user).select_related("month").order_by(
        "-month__year", "-month__month"
    )

    context = {
        "reports": reports,
    }
    return render(request, "expenses/expense_list.html", context)


@login_required
def expense_detail(request, pk):
    """View a specific expense report."""
    report = get_object_or_404(
        ExpenseReport.objects.select_related("month", "employee"),
        pk=pk,
    )

    # Check permissions
    if report.employee != request.user:
        if not request.user.groups.filter(
            name__in=["office_manager", "managing_partner", "payroll_partner", "accountants"]
        ).exists():
            return HttpResponseForbidden("You don't have permission to view this expense report.")

    items = report.items.select_related("category").prefetch_related("receipts").order_by("date")
    mileage_entries = report.mileage_entries.order_by("date")

    context = {
        "report": report,
        "items": items,
        "mileage_entries": mileage_entries,
    }
    return render(request, "expenses/expense_detail.html", context)


@login_required
def expense_edit(request, pk):
    """Edit an expense report."""
    report = get_object_or_404(
        ExpenseReport.objects.select_related("month", "employee"),
        pk=pk,
    )

    if report.employee != request.user:
        return HttpResponseForbidden("You can only edit your own expense reports.")

    if not report.is_editable:
        messages.error(request, "This expense report cannot be edited.")
        return redirect("expenses:expense_detail", pk=pk)

    items = report.items.select_related("category").prefetch_related("receipts").order_by("date")
    mileage_entries = report.mileage_entries.order_by("date")
    categories = ExpenseCategory.objects.filter(active=True).order_by("name")

    context = {
        "report": report,
        "items": items,
        "mileage_entries": mileage_entries,
        "categories": categories,
    }
    return render(request, "expenses/expense_edit.html", context)


@login_required
@require_POST
def expense_add_item(request, pk):
    """HTMX: Add a new expense item."""
    report = get_object_or_404(ExpenseReport, pk=pk, employee=request.user)

    if not report.is_editable:
        return HttpResponse("Report is not editable", status=400)

    try:
        from datetime import datetime
        date = datetime.strptime(request.POST.get("date"), "%Y-%m-%d").date()
        amount = Decimal(request.POST.get("amount", "0"))
        category_id = request.POST.get("category")
        description = request.POST.get("description", "").strip()
        client = request.POST.get("client", "").strip()
        paper_receipt = request.POST.get("paper_receipt_delivered") == "on"
    except (ValueError, InvalidOperation) as e:
        return HttpResponse(f"Invalid data: {e}", status=400)

    if amount <= 0:
        return HttpResponse("Amount must be greater than 0", status=400)

    category = get_object_or_404(ExpenseCategory, pk=category_id, active=True)

    item = ExpenseItem.objects.create(
        report=report,
        category=category,
        date=date,
        amount=amount,
        description=description,
        client=client,
        paper_receipt_delivered=paper_receipt,
    )

    # Handle uploaded receipts
    files = request.FILES.getlist("receipts")
    for f in files:
        ExpenseReceipt.objects.create(
            expense_item=item,
            file=f,
            original_filename=f.name,
        )

    html = render_to_string("expenses/partials/expense_item_row.html", {
        "item": item,
        "report": report,
    }, request=request)

    response = HttpResponse(html)
    response["HX-Trigger"] = json.dumps({"updateTotals": True})
    return response


@login_required
@require_POST
def expense_delete_item(request, pk, item_id):
    """HTMX: Delete an expense item."""
    report = get_object_or_404(ExpenseReport, pk=pk, employee=request.user)

    if not report.is_editable:
        return HttpResponse("Report is not editable", status=400)

    item = get_object_or_404(ExpenseItem, pk=item_id, report=report)
    item.delete()

    response = HttpResponse("")
    response["HX-Trigger"] = json.dumps({"updateTotals": True})
    return response


@login_required
@require_POST
def expense_upload_receipt(request, pk, item_id):
    """HTMX: Upload receipt(s) to an expense item."""
    report = get_object_or_404(ExpenseReport, pk=pk, employee=request.user)

    if not report.is_editable:
        return HttpResponse("Report is not editable", status=400)

    item = get_object_or_404(ExpenseItem, pk=item_id, report=report)

    files = request.FILES.getlist("receipts")
    created_receipts = []

    for f in files:
        receipt = ExpenseReceipt.objects.create(
            expense_item=item,
            file=f,
            original_filename=f.name,
        )
        created_receipts.append(receipt)

    # Return updated receipts HTML
    html = render_to_string("expenses/partials/receipt_list.html", {
        "item": item,
        "report": report,
    }, request=request)

    return HttpResponse(html)


@login_required
@require_POST
def expense_delete_receipt(request, pk, receipt_id):
    """HTMX: Delete a receipt."""
    report = get_object_or_404(ExpenseReport, pk=pk, employee=request.user)

    if not report.is_editable:
        return HttpResponse("Report is not editable", status=400)

    receipt = get_object_or_404(ExpenseReceipt, pk=receipt_id, expense_item__report=report)
    receipt.file.delete()
    receipt.delete()

    return HttpResponse("")


@login_required
@require_POST
def expense_add_mileage(request, pk):
    """HTMX: Add a mileage entry."""
    report = get_object_or_404(ExpenseReport, pk=pk, employee=request.user)

    if not report.is_editable:
        return HttpResponse("Report is not editable", status=400)

    try:
        from datetime import datetime
        date = datetime.strptime(request.POST.get("date"), "%Y-%m-%d").date()
        miles = Decimal(request.POST.get("miles", "0"))
        description = request.POST.get("description", "").strip()
    except (ValueError, InvalidOperation) as e:
        return HttpResponse(f"Invalid data: {e}", status=400)

    if miles <= 0:
        return HttpResponse("Miles must be greater than 0", status=400)

    entry = MileageEntry.objects.create(
        report=report,
        date=date,
        miles=miles,
        description=description,
    )

    html = render_to_string("expenses/partials/mileage_row.html", {
        "entry": entry,
        "report": report,
    }, request=request)

    response = HttpResponse(html)
    response["HX-Trigger"] = json.dumps({"updateTotals": True})
    return response


@login_required
@require_POST
def expense_delete_mileage(request, pk, entry_id):
    """HTMX: Delete a mileage entry."""
    report = get_object_or_404(ExpenseReport, pk=pk, employee=request.user)

    if not report.is_editable:
        return HttpResponse("Report is not editable", status=400)

    entry = get_object_or_404(MileageEntry, pk=entry_id, report=report)
    entry.delete()

    response = HttpResponse("")
    response["HX-Trigger"] = json.dumps({"updateTotals": True})
    return response


@login_required
@require_GET
def expense_totals(request, pk):
    """HTMX: Get updated totals."""
    report = get_object_or_404(ExpenseReport, pk=pk)

    if report.employee != request.user:
        if not request.user.groups.filter(name="office_manager").exists():
            return HttpResponseForbidden()

    report.refresh_from_db()
    return JsonResponse({
        "total_expenses": str(report.total_expenses),
        "total_mileage": str(report.total_mileage_amount),
        "grand_total": str(report.grand_total),
    })


@login_required
@require_POST
def expense_submit(request, pk):
    """Submit expense report for review."""
    report = get_object_or_404(ExpenseReport, pk=pk)

    if report.employee != request.user:
        return HttpResponseForbidden("You can only submit your own expense reports.")

    # Validate receipts
    missing_receipts = []
    for item in report.items.all():
        if item.requires_receipt and not item.receipt_requirement_met:
            missing_receipts.append(item)

    if missing_receipts:
        messages.error(
            request,
            f"Cannot submit: {len(missing_receipts)} expense(s) over ${report.items.first().category.receipt_required_threshold} require receipts."
        )
        return redirect("expenses:expense_edit", pk=pk)

    try:
        with transaction.atomic():
            report.submit()
            ReviewAction.log_action(
                report,
                ReviewAction.ActionType.SUBMITTED,
                request.user,
                request.POST.get("notes", "")
            )
        messages.success(request, "Expense report submitted successfully!")
    except Exception as e:
        messages.error(request, str(e))

    return redirect("expenses:expense_detail", pk=pk)


@login_required
@require_POST
def expense_save_notes(request, pk):
    """HTMX: Save employee notes."""
    report = get_object_or_404(ExpenseReport, pk=pk, employee=request.user)

    if not report.is_editable:
        return HttpResponse("Report is not editable", status=400)

    notes = request.POST.get("employee_notes", "")
    report.employee_notes = notes
    report.save(update_fields=["employee_notes", "updated_at"])

    return HttpResponse('<span class="text-success"><i class="bi bi-check"></i> Saved</span>')
