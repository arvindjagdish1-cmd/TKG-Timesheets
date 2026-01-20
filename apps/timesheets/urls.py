from django.urls import path

from . import views

app_name = "timesheets"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),

    # Timesheet CRUD
    path("timesheets/", views.timesheet_list, name="timesheet_list"),
    path("timesheet/<int:pk>/", views.timesheet_detail, name="timesheet_detail"),
    path("timesheet/<int:pk>/edit/", views.timesheet_edit, name="timesheet_edit"),
    path("timesheet/<int:pk>/submit/", views.timesheet_submit, name="timesheet_submit"),

    # HTMX endpoints
    path("timesheet/<int:pk>/save-entry/", views.timesheet_save_entry, name="timesheet_save_entry"),
    path("timesheet/<int:pk>/add-line/", views.timesheet_add_line, name="timesheet_add_line"),
    path("timesheet/<int:pk>/delete-line/<int:line_id>/", views.timesheet_delete_line, name="timesheet_delete_line"),
    path("timesheet/<int:pk>/save-notes/", views.timesheet_save_notes, name="timesheet_save_notes"),
]
