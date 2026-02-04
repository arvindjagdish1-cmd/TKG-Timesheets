from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_add_profile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalemployeeprofile",
            name="employee_number",
            field=models.CharField(
                blank=True,
                help_text="Employee number used in payroll exports (optional).",
                max_length=50,
                verbose_name="employee number",
            ),
        ),
        migrations.AddField(
            model_name="historicalemployeeprofile",
            name="initials",
            field=models.CharField(
                blank=True,
                help_text="Unique initials used in partner reporting.",
                max_length=10,
                null=True,
                verbose_name="initials",
            ),
        ),
        migrations.AddField(
            model_name="historicalemployeeprofile",
            name="active",
            field=models.BooleanField(
                default=True,
                help_text="Whether the employee is active for reporting.",
                verbose_name="active",
            ),
        ),
    ]
