from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

ROLE_GROUPS = [
    "employees",
    "office_manager",
    "managing_partner",
    "payroll_partner",
    "accountants",
]

class Command(BaseCommand):
    help = "Create default role groups."

    def handle(self, *args, **options):
        for name in ROLE_GROUPS:
            Group.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS(f"Ensured groups exist: {', '.join(ROLE_GROUPS)}"))
