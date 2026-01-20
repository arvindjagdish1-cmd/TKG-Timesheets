from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    # Dashboard
    path("reviews/", views.review_dashboard, name="dashboard"),
    path("reviews/pending/", views.pending_reviews, name="pending"),

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
]
