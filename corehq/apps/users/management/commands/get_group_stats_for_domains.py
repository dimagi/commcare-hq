from django.core.management.base import BaseCommand

from corehq.apps.groups.models import Group


class Command(BaseCommand):
    help = "gets the number of mobile workers and number of groups by domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        user_to_group = {}
        for group in Group.by_domain(domain):
            if group.case_sharing and group.users:
                for user_id in group.users:
                    if user_id not in user_to_group:
                        user_to_group[user_id] = 1
                    else:
                        user_to_group[user_id] += 1
        for user_id, num_groups in user_to_group.items():
            print(f"{user_id}\t{num_groups}")
