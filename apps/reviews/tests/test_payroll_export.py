from django.test import TestCase

from apps.accounts.models import User, EmployeeProfile
from apps.timesheets.models import TimesheetUpload
from apps.reviews.views import _build_payroll_rows


class PayrollExportTests(TestCase):
    def test_marketing_allocation(self):
        user = User.objects.create(email="test@thekeystonegroup.com", first_name="Test", last_name="User")
        EmployeeProfile.objects.create(user=user, initials="TU", employee_number="1001")

        TimesheetUpload.objects.create(
            user=user,
            year=2026,
            month=1,
            status=TimesheetUpload.Status.SUBMITTED,
            parsed_json={
                "expenses": {
                    "items": [
                        {
                            "bucket": "Marketing - Meals",
                            "charge_code": "CHI-BNK-LEAD",
                            "amount": 100,
                        },
                        {
                            "bucket": "Marketing - General",
                            "charge_code": "GEN-OTHER",
                            "amount": 50,
                        },
                    ],
                    "totals_by_bucket": {
                        "Travel": 20,
                    },
                }
            },
        )

        rows, flags = _build_payroll_rows(2026, 1)
        row = next(r for r in rows if r["Person"] == "Test User")

        self.assertEqual(float(row["MKT Banking — Chicago-Lead"]), 100.0)
        self.assertEqual(float(row["MKT General — General"]), 50.0)
        self.assertEqual(float(row["TKG — Travel"]), 20.0)
        self.assertEqual(float(row["Expenses — Total"]), 170.0)
        self.assertEqual(flags, [])
