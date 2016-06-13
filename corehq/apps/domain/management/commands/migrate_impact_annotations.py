from django.core.management.base import BaseCommand
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = "Migrates wam and pam eligibility from apps to domains"
    args = ""

    def handle(self, *args, **options):
        print "Migrating impact annotations"

        for domain in Domain.get_all():
            for app in domain.applications():
                if app.amplifies_project == "yes":
                    domain.internal.amplifies_project = "yes"
                elif app.amplifies_project == "no" and domain.internal.amplifies_project != "yes":
                    domain.internal.amplifies_project = "no"
                if app.amplifies_workers == "yes":
                    domain.internal.amplifies_workers = "yes"
                elif app.amplifies_workers == "no" and domain.internal.amplifies_workers != "yes":
                    domain.internal.amplifies_workers = "no"
            domain.save()
