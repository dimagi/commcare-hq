from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Migrates wam and pam eligibility from apps to domains"

    def handle(self, **options):
        print("Migrating impact annotations")

        for domain in Domain.get_all():
            changed = False
            for app in domain.applications():
                if app.amplifies_project == "yes":
                    domain.internal.amplifies_project = "yes"
                    changed = True
                elif app.amplifies_project == "no" and domain.internal.amplifies_project != "yes":
                    domain.internal.amplifies_project = "no"
                    changed = True
                if app.amplifies_workers == "yes":
                    domain.internal.amplifies_workers = "yes"
                    changed = True
                elif app.amplifies_workers == "no" and domain.internal.amplifies_workers != "yes":
                    domain.internal.amplifies_workers = "no"
                    changed = True
            if changed:
                domain.save()
