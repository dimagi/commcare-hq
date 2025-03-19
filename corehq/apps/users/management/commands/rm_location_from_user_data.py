# One-off migration, Nov 2024

from django.core.management.base import BaseCommand
from django.db.models import Q
from corehq.apps.domain_migration_flags.api import once_off_migration
from corehq.apps.users.user_data import SQLUserData

from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Remove now-stale location info from SQLUserData.data field"

    def handle(self, *args, **options):
        do_migration()


@once_off_migration("rm_location_from_user_data")
def do_migration():
    rows_need_migration = SQLUserData.objects.filter(Q(data__has_key='commcare_location_id'))

    for user_data in with_progress_bar(rows_need_migration):
        data = user_data.data
        keys_to_remove = ['commcare_location_id', 'commcare_location_ids', 'commcare_primary_case_sharing_id']

        modified = False
        for key in keys_to_remove:
            if key in data:
                del data[key]
                modified = True

        if modified:
            user_data.save()
