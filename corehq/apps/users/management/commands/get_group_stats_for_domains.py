from django.core.management.base import BaseCommand

from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser


class Command(BaseCommand):
    help = "gets the number of mobile workers and number of groups by domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        # figure out how many unique devices each user has signed into and number of groups
        user_to_group = {}
        self.stdout.write("User ID\tNum Groups\tNum Devices")
        for group in Group.by_domain(domain):
            if group.case_sharing and group.users:
                for user_id in group.users:
                    if user_id not in user_to_group:
                        user_to_group[user_id] = 1
                    else:
                        user_to_group[user_id] += 1
        for user_id, num_groups in user_to_group.items():
            if num_groups > 1:
                cc_user = CommCareUser.get_by_user_id(user_id)
                num_devices = len(cc_user.devices)
                if num_devices > 2 and cc_user.is_active:
                    self.stdout.write(f"{user_id}\t{num_groups}\t{num_devices}")
