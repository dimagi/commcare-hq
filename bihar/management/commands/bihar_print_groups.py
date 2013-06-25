from django.core.management import BaseCommand
from bihar.utils import get_groups_for_group
from corehq.apps.groups.models import Group


class Command(BaseCommand):
    """Nice for finding all related groups"""
    def handle(self, *args, **options):
        domain = args[0]
        group_name = args[1]
        group_id = Group.by_name(domain, name=group_name).get_id
        groups = get_groups_for_group(group_id)

        for group in groups:
            if group.case_sharing or group.get_id == group_id:
                print group.get_id, group.name
