import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ManagingPartnerLayout",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.IntegerField()),
                ("month", models.IntegerField()),
                ("employee_order", models.JSONField(blank=True, default=list, help_text="Ordered list of User PKs for column ordering.")),
                ("client_order", models.JSONField(blank=True, default=list, help_text="Ordered list of client charge codes for row ordering.")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "managing partner layout",
                "verbose_name_plural": "managing partner layouts",
                "unique_together": {("year", "month")},
            },
        ),
    ]
