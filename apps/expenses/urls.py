from django.urls import path

from . import views

app_name = "expenses"

urlpatterns = [
    # Expense Report CRUD
    path("expenses/", views.expense_list, name="expense_list"),
    path("expense/<int:pk>/", views.expense_detail, name="expense_detail"),
    path("expense/<int:pk>/edit/", views.expense_edit, name="expense_edit"),
    path("expense/<int:pk>/submit/", views.expense_submit, name="expense_submit"),
    path("expense/<int:pk>/save-notes/", views.expense_save_notes, name="expense_save_notes"),

    # HTMX endpoints - Items
    path("expense/<int:pk>/add-item/", views.expense_add_item, name="expense_add_item"),
    path("expense/<int:pk>/delete-item/<int:item_id>/", views.expense_delete_item, name="expense_delete_item"),

    # HTMX endpoints - Receipts
    path("expense/<int:pk>/upload-receipt/<int:item_id>/", views.expense_upload_receipt, name="expense_upload_receipt"),
    path("expense/<int:pk>/delete-receipt/<int:receipt_id>/", views.expense_delete_receipt, name="expense_delete_receipt"),

    # HTMX endpoints - Mileage
    path("expense/<int:pk>/add-mileage/", views.expense_add_mileage, name="expense_add_mileage"),
    path("expense/<int:pk>/delete-mileage/<int:entry_id>/", views.expense_delete_mileage, name="expense_delete_mileage"),

    # HTMX endpoints - Totals
    path("expense/<int:pk>/totals/", views.expense_totals, name="expense_totals"),
]
