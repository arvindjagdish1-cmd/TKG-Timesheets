from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = "Load reference fixtures (charge codes, expense categories)."

    def handle(self, *args, **options):
        call_command("loaddata", "charge_codes.json")
        call_command("loaddata", "expense_categories.json")
        self.stdout.write(self.style.SUCCESS("Loaded reference fixtures."))
