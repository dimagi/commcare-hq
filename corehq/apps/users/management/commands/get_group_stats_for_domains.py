from django.core.management.base import BaseCommand

from corehq.apps.groups.models import Group


class Command(BaseCommand):
    help = "gets the number of mobile workers and number of groups by domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        for group in Group.by_domain(domain):
            if group.case_sharing and group.users:
                self.stdout.write(f"{group.name}\t{group.get_id}\t{len(group.users)}")
