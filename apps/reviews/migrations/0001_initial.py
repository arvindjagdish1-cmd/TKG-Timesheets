import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReviewAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_id", models.PositiveIntegerField()),
                ("action", models.CharField(choices=[("SUBMITTED", "Submitted"), ("APPROVED", "Approved"), ("RETURNED", "Returned"), ("RESUBMITTED", "Re-submitted"), ("COMMENT", "Comment")], max_length=15, verbose_name="action")),
                ("comment", models.TextField(blank=True, verbose_name="comment")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="created at")),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="review_actions", to=settings.AUTH_USER_MODEL)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
            ],
            options={
                "verbose_name": "review action",
                "verbose_name_plural": "review actions",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="reviewaction",
            index=models.Index(fields=["content_type", "object_id"], name="reviews_rev_content_idx"),
        ),
        migrations.CreateModel(
            name="ReviewComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_id", models.PositiveIntegerField()),
                ("text", models.TextField(verbose_name="comment")),
                ("is_internal", models.BooleanField(default=False, help_text="If true, only visible to office managers/reviewers.", verbose_name="internal only")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="created at")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="updated at")),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="review_comments", to=settings.AUTH_USER_MODEL)),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
            ],
            options={
                "verbose_name": "review comment",
                "verbose_name_plural": "review comments",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="reviewcomment",
            index=models.Index(fields=["content_type", "object_id"], name="reviews_com_content_idx"),
        ),
    ]
