"""
Safety-net backfill of employee_number by last name + first name,
in case the initials-based migration (0004) was faked or initials
didn't match exactly.
"""
from django.db import migrations


EE_NUMBERS_BY_NAME = {
    ("Adidam", "Keshava"): "186",
    ("Bartsch", "Derek"): "165",
    ("Blum", "Ryan"): "129",
    ("Budicin", "Ryan"): "121",
    ("Burkard", "Ryan"): "72",
    ("Butler", "Alyssa"): "92",
    ("Caracciolo", "Tori"): "187",
    ("Clark", "Travis"): "176",
    ("Clark", "William"): "173",
    ("Dion", "Samuel"): "103",
    ("Dunne", "Barry"): "10",
    ("Farrell", "Evan"): "73",
    ("Foster", "Nathan"): "167",
    ("Gallick", "Michael"): "43",
    ("Harig", "Emily"): "86",
    ("Harper", "Anna"): "172",
    ("Healy", "Ava"): "184",
    ("Hinkamp", "Matthew"): "95",
    ("Jacobs", "Bret"): "141",
    ("Jagdish", "Arvind"): "157",
    ("Jeannin", "Christophe"): "5",
    ("Jordan", "Kayla"): "152",
    ("Kandimalla", "Nihar"): "128",
    ("Kaswan Meilijson", "Alex"): "185",
    ("Kaswan", "Alex"): "185",
    ("Knopman", "Aaron"): "130",
    ("Malik", "Adil"): "131",
    ("Mathisson", "Jonah"): "171",
    ("Matthison", "Jonah"): "171",
    ("McCurdy", "Matt"): "188",
    ("Miller", "Danielle"): "38",
    ("Mocny", "Julia"): "159",
    ("Monteferrante", "Katherine"): "147",
    ("Moxon", "Elizabeth"): "155",
    ("Pavlick", "Jared"): "145",
    ("Prager", "Steven"): "150",
    ("Rajski", "Pauline"): "175",
    ("Samples", "Jansyn"): "160",
    ("Shah", "Amar"): "50",
    ("Steilen", "Alex"): "104",
    ("Stewart", "Brian"): "4",
    ("Tahawi", "Yusef"): "143",
    ("Tamer", "Jose"): "174",
    ("Tierney", "Ryan"): "144",
    ("Urbaites", "Anthony"): "66",
    ("Zito", "Joseph"): "6",
}


def populate(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    EmployeeProfile = apps.get_model("accounts", "EmployeeProfile")

    for profile in EmployeeProfile.objects.select_related("user").all():
        if profile.employee_number:
            continue
        user = profile.user
        last = (user.last_name or "").strip()
        first = (user.first_name or "").strip()
        ee_num = EE_NUMBERS_BY_NAME.get((last, first))
        if ee_num:
            profile.employee_number = ee_num
            profile.save(update_fields=["employee_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_populate_employee_numbers"),
    ]

    operations = [
        migrations.RunPython(populate, migrations.RunPython.noop),
    ]
