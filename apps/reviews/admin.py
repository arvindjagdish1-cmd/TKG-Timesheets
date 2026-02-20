from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import ReviewAction, ReviewComment, PlannedHire


@admin.register(ReviewAction)
class ReviewActionAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "content_type", "object_id", "created_at")
    list_filter = ("action", "content_type", "created_at")
    search_fields = ("actor__email", "comment")
    ordering = ("-created_at",)
    readonly_fields = ("content_type", "object_id", "action", "actor", "created_at")
    date_hierarchy = "created_at"


@admin.register(ReviewComment)
class ReviewCommentAdmin(admin.ModelAdmin):
    list_display = ("author", "short_text", "content_type", "object_id", "is_internal", "created_at")
    list_filter = ("is_internal", "content_type", "created_at")
    search_fields = ("author__email", "text")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    @admin.display(description="Comment")
    def short_text(self, obj):
        return obj.text[:60] + "..." if len(obj.text) > 60 else obj.text


# Generic inlines for use in Timesheet/ExpenseReport admin
class ReviewActionInline(GenericTabularInline):
    model = ReviewAction
    extra = 0
    fields = ("action", "actor", "comment", "created_at")
    readonly_fields = ("action", "actor", "comment", "created_at")
    ordering = ("-created_at",)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class ReviewCommentInline(GenericTabularInline):
    model = ReviewComment
    extra = 0
    fields = ("author", "text", "is_internal", "created_at")
    readonly_fields = ("author", "created_at")
    ordering = ("created_at",)


@admin.register(PlannedHire)
class PlannedHireAdmin(admin.ModelAdmin):
    list_display = ("display_name", "active", "created_by", "created_at")
    list_filter = ("active",)
    search_fields = ("display_name",)
