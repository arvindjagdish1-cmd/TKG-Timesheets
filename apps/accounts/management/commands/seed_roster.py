from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.accounts.models import EmployeeProfile


ROSTER = [
    ("ashah@thekeystonegroup.com", "Amar", "Shah", "managing_partner"),
    ("bstewart@thekeystonegroup.com", "Brian", "Stewart", "payroll_partner"),
    ("mgallick@thekeystonegroup.com", "Mike", "Gallick", "office_manager"),
    ("rburkard@thekeystonegroup.com", "Ryan", "Burkard", "partner"),
    ("efarrell@thekeystonegroup.com", "Evan", "Farrell", "partner"),
    ("cjeannin@thekeystonegroup.com", "Christophe", "Jeannin", "partner"),
    ("mmccurdy@thekeystonegroup.com", "Matt", "McCurdy", "partner"),
    ("dmiller@thekeystonegroup.com", "Danielle", "Miller", "partner"),
    ("jzito@thekeystonegroup.com", "Joe", "Zito", "partner"),
    ("dbartsch@thekeystonegroup.com", "Derek", "Bartsch", "business_development"),
    ("bdunne@thekeystonegroup.com", "Barry", "Dunne", "business_development"),
    ("mseitz@thekeystonegroup.com", "Matt", "Seitz", "executive_advisor"),
    ("mtopa@thekeystonegroup.com", "Mike", "Topa", "executive_advisor"),
    ("abutler@thekeystonegroup.com", "Alyssa", "Butler", "senior_principal"),
    ("sdion@thekeystonegroup.com", "Sam", "Dion", "senior_principal"),
    ("eharig@thekeystonegroup.com", "Emily", "Harig", "senior_principal"),
    ("mhinkamp@thekeystonegroup.com", "Matt", "Hinkamp", "senior_principal"),
    ("bjacobs@thekeystonegroup.com", "Bret", "Jacobs", "senior_principal"),
    ("sprager@thekeystonegroup.com", "Steven", "Prager", "senior_principal"),
    ("asteilen@thekeystonegroup.com", "Alex", "Steilen", "senior_principal"),
    ("jtamer@thekeystonegroup.com", "Joe", "Tamer", "senior_principal"),
    ("rtierney@thekeystonegroup.com", "Ryan", "Tierney", "senior_principal"),
    ("aurbaites@thekeystonegroup.com", "Anthony", "Urbaites", "senior_principal"),
    ("nkandimalla@thekeystonegroup.com", "Nihar", "Kandimalla", "senior_principal"),
    ("rbudicin@thekeystonegroup.com", "Ryan", "Budicin", "senior_associate"),
    ("kgutwein@thekeystonegroup.com", "Kurt", "Gutwein", "senior_associate"),
    ("nfoster@thekeystonegroup.com", "Nathan", "Foster", "senior_associate"),
    ("kjordan@thekeystonegroup.com", "Kayla", "Jordan", "senior_associate"),
    ("aknopman@thekeystonegroup.com", "Aaron", "Knopman", "senior_associate"),
    ("rblum@thekeystonegroup.com", "Ryan", "Blum", "associate"),
    ("hmalik@thekeystonegroup.com", "Haaris", "Malik", "associate"),
    ("ytahawi@thekeystonegroup.com", "Yusef", "Tahawi", "associate"),
    ("tclark@thekeystonegroup.com", "Travis", "Clark", "senior_analyst"),
    ("jmocny@thekeystonegroup.com", "Julia", "Mocny", "senior_analyst"),
    ("kmonteferrante@thekeystonegroup.com", "Katie", "Monteferrante", "senior_analyst"),
    ("jpavlick@thekeystonegroup.com", "Jared", "Pavlick", "senior_analyst"),
    ("jsamples@thekeystonegroup.com", "Jansyn", "Samples", "senior_analyst"),
    ("kadidam@thekeystonegroup.com", "Keshava", "Adidam", "analyst"),
    ("tcaracciolo@thekeystonegroup.com", "Tori", "Caracciolo", "analyst"),
    ("wclark@thekeystonegroup.com", "Will", "Clark", "analyst"),
    ("aharper@thekeystonegroup.com", "Anna", "Harper", "analyst"),
    ("ahealy@thekeystonegroup.com", "Ava", "Healy", "analyst"),
    ("akaswan@thekeystonegroup.com", "Alex", "Kaswan", "analyst"),
    ("jmathisson@thekeystonegroup.com", "Jonah", "Mathisson", "analyst"),
    ("prajski@thekeystonegroup.com", "Paulina", "Rajski", "analyst"),
    ("bmoxon@thekeystonegroup.com", "Beth", "Moxon", "program_coordinator"),
]


ROLE_GROUP_MAP = {
    "managing_partner": "managing_partner",
    "payroll_partner": "payroll_partner",
    "office_manager": "office_manager",
}


class Command(BaseCommand):
    help = "Seed roster users and assign roles."

    def handle(self, *args, **options):
        User = get_user_model()
        default_group, _ = Group.objects.get_or_create(name="employees")

        created = 0
        updated = 0

        initials_taken = set(
            EmployeeProfile.objects.exclude(initials="").values_list("initials", flat=True)
        )

        for email, first_name, last_name, title in ROSTER:
            user, was_created = User.objects.get_or_create(
                email=email.lower(),
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "is_active": True,
                },
            )
            if not was_created:
                user.first_name = first_name
                user.last_name = last_name
                user.is_active = True
                user.save(update_fields=["first_name", "last_name", "is_active"])
                updated += 1
            else:
                created += 1

            profile, _ = EmployeeProfile.objects.get_or_create(user=user)
            profile.title = title.replace("_", " ").title()
            profile.active = True
            if not profile.initials:
                profile.initials = _unique_initials(first_name, last_name, initials_taken)
                initials_taken.add(profile.initials)
            profile.save(update_fields=["title", "active", "initials"])

            group_name = ROLE_GROUP_MAP.get(title)
            if group_name:
                group, _ = Group.objects.get_or_create(name=group_name)
                user.groups.add(group)
            else:
                user.groups.add(default_group)

        self.stdout.write(self.style.SUCCESS(f"Created {created} users, updated {updated} users."))


def _unique_initials(first_name, last_name, taken):
    base = f"{(first_name[:1] or '').upper()}{(last_name[:1] or '').upper()}"
    if base and base not in taken:
        return base
    if not base:
        base = "NA"
    idx = 2
    candidate = base
    while candidate in taken:
        candidate = f"{base}{idx}"
        idx += 1
    return candidate
