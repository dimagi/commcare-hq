from django.core.management.base import BaseCommand

from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser


class Command(BaseCommand):
    help = "gets the number of mobile workers and number of groups by domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        # figure out how many unique devices each user has signed into and number of groups
        group_lengths_users_groups = {}
        all_user_ids = []
        self.stdout.write("User ID\tNum Groups\tNum Devices\tNum Users in Group\tIs Unique")
        for group in Group.by_domain(domain):
            num_users_in_group = len(group.users)
            if num_users_in_group > 2:
                # likely test users
                continue
            if num_users_in_group not in group_lengths_users_groups:
                group_lengths_users_groups[num_users_in_group] = {}

            if group.case_sharing and group.users:
                for user_id in group.users:
                    if user_id not in group_lengths_users_groups[num_users_in_group]:
                        all_user_ids.append(user_id)
                        group_lengths_users_groups[num_users_in_group][user_id] = 0

                    group_lengths_users_groups[num_users_in_group][user_id] += 1
        for num_users_in_group, user_to_group in group_lengths_users_groups.items():
            for user_id, num_groups in user_to_group.items():
                is_unique = "YES" if all_user_ids.count(user_id) == 1 else "NO"
                if num_groups > 1:
                    cc_user = CommCareUser.get_by_user_id(user_id)
                    num_devices = len(cc_user.devices)
                    if num_devices > 2 and cc_user.is_active:
                        self.stdout.write(f"{user_id}\t{num_groups}\t{num_devices}"
                                          f"\t{num_users_in_group}\t{is_unique}")
