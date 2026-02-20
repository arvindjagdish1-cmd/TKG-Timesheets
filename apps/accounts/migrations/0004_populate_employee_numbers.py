"""
Populate EmployeeProfile.employee_number from Payroll Partner data.
"""
from django.db import migrations


EE_NUMBERS_BY_INITIALS = {
    "KA": "186",
    "DB": "165",
    "RBL": "129",
    "RBU": "121",
    "RB": "72",
    "ABU": "92",
    "TCa": "187",
    "TC": "176",
    "WC": "173",
    "SD": "103",
    "BD": "10",
    "EF": "73",
    "NF": "167",
    "MG": "43",
    "EH": "86",
    "AH": "172",
    "AHE": "184",
    "MH": "95",
    "BJ": "141",
    "AJ": "157",
    "CJ": "5",
    "KJ": "152",
    "NK": "128",
    "AKM": "185",
    "AK": "130",
    "HM": "131",
    "JMA": "171",
    "MM": "188",
    "DM": "38",
    "JMO": "159",
    "KM": "147",
    "BM": "155",
    "JP": "145",
    "SP": "150",
    "PR": "175",
    "JSA": "160",
    "AS": "50",
    "AST": "104",
    "BS": "4",
    "YT": "143",
    "JT": "174",
    "RT": "144",
    "AU": "66",
    "JZ": "6",
}


def populate(apps, schema_editor):
    EmployeeProfile = apps.get_model("accounts", "EmployeeProfile")
    for profile in EmployeeProfile.objects.filter(initials__isnull=False).exclude(initials=""):
        ee_num = EE_NUMBERS_BY_INITIALS.get(profile.initials)
        if ee_num and not profile.employee_number:
            profile.employee_number = ee_num
            profile.save(update_fields=["employee_number"])


def rollback(apps, schema_editor):
    EmployeeProfile = apps.get_model("accounts", "EmployeeProfile")
    known_initials = set(EE_NUMBERS_BY_INITIALS.keys())
    EmployeeProfile.objects.filter(initials__in=known_initials).update(employee_number="")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_add_history_fields"),
    ]

    operations = [
        migrations.RunPython(populate, rollback),
    ]
