from django.core.management import BaseCommand
from bihar.utils import get_groups_for_group
from corehq.apps.groups.models import Group


class Command(BaseCommand):
    """Nice for finding all related groups"""
    def handle(self, *args, **options):
        domain = args[0]
        group_name = args[1]
        primary_group = Group.by_name(domain, name=group_name)
        groups = get_groups_for_group(primary_group)

        for group in groups:
            if group.case_sharing or group.get_id == group.get_id:
                print group.get_id, group.name
