import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("reviews", "0002_managingpartnerlayout"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlannedHire",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "display_name",
                    models.CharField(
                        help_text='Label shown in the column header, e.g. "Jr. Experienced Hire".',
                        max_length=150,
                    ),
                ),
                (
                    "active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive planned hires are hidden from the spreadsheet.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "planned hire",
                "verbose_name_plural": "planned hires",
                "ordering": ["display_name"],
            },
        ),
    ]
