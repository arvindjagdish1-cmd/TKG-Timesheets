from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),

    # App routes
    path("", include("apps.timesheets.urls")),
    path("", include("apps.expenses.urls")),
    path("", include("apps.reviews.urls")),
    path("", include("apps.exports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
