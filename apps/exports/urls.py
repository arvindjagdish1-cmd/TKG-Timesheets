from django.urls import path

from . import views

app_name = "exports"

urlpatterns = [
    path("exports/", views.export_dashboard, name="export_dashboard"),
    path("exports/list/", views.export_list, name="export_list"),
    path("exports/timesheets/generate/", views.generate_timesheet_exports, name="generate_timesheets"),
    path("exports/expenses/generate/", views.generate_expense_exports, name="generate_expenses"),
    path("exports/download/<int:pk>/", views.download_export, name="download"),
]
