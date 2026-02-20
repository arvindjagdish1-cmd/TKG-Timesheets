from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    # Office Manager Dashboard
    path("reviews/", views.review_dashboard, name="dashboard"),
    path("reviews/pending/", views.pending_reviews, name="pending"),
    path(
        "reviews/employee/<int:user_id>/<int:year>/<int:month>/",
        views.office_employee_detail,
        name="office_employee_detail",
    ),
    path("reviews/upload/<int:pk>/return/", views.office_return_upload, name="office_return_upload"),
    path("reviews/upload/<int:pk>/approve/", views.office_approve_upload, name="office_approve_upload"),

    # Timesheet review
    path("reviews/timesheet/<int:pk>/", views.review_timesheet, name="review_timesheet"),
    path("reviews/timesheet/<int:pk>/approve/", views.approve_timesheet, name="approve_timesheet"),
    path("reviews/timesheet/<int:pk>/return/", views.return_timesheet, name="return_timesheet"),

    # Expense review
    path("reviews/expense/<int:pk>/", views.review_expense, name="review_expense"),
    path("reviews/expense/<int:pk>/approve/", views.approve_expense, name="approve_expense"),
    path("reviews/expense/<int:pk>/return/", views.return_expense, name="return_expense"),

    # Comments
    path("reviews/comment/<str:content_type>/<int:pk>/", views.add_comment, name="add_comment"),

    # Managing Partner Views
    path("partner/", views.managing_partner_dashboard, name="partner_dashboard"),
    path("partner/daily/", views.daily_summary, name="daily_summary"),
    path("partner/daily/<int:period_id>/", views.daily_summary, name="daily_summary_period"),
    path("partner/category/", views.category_summary, name="category_summary"),
    path("partner/category/<int:period_id>/", views.category_summary, name="category_summary_period"),
    path("partner/employees/", views.employee_summary, name="employee_summary"),
    path("partner/expenses/", views.employee_expenses, name="employee_expenses"),
    path("partner/export/<int:year>/<int:month>/", views.partner_export_xlsx, name="partner_export_xlsx"),

    # Managing Partner Spreadsheet
    path("mp/", views.mp_spreadsheet, name="mp_spreadsheet"),
    path("mp/reorder/", views.mp_reorder, name="mp_reorder"),
    path("mp/export/<int:year>/<int:month>/", views.mp_export_xlsx, name="mp_export_xlsx"),
    path("mp/planned-hire/add/", views.mp_add_planned_hire, name="mp_add_planned_hire"),
    path("mp/planned-hire/<int:pk>/delete/", views.mp_delete_planned_hire, name="mp_delete_planned_hire"),

    # Payroll Partner Views
    path("payroll/", views.payroll_dashboard, name="payroll_dashboard"),
    path("payroll/export/<int:year>/<int:month>/", views.payroll_export, name="payroll_export"),
]
