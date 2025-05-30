from django.core.management.base import BaseCommand

from corehq.apps.domain_migration_flags.api import once_off_migration
from corehq.apps.es.users import UserES, user_adapter
from corehq.apps.es.utils import get_user_domain_memberships
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = ("Migrates User ES models: add user_domain_memberships")

    def handle(self, **options):
        _run_migration()


@once_off_migration("populate_user_domain_memberships")
def _run_migration():
    query_set = UserES().show_inactive()
    for user in with_progress_bar(query_set.scroll_ids_to_disk_and_iter_docs(), query_set.count()):
        if 'user_domain_memberships' not in user:
            memberships = get_user_domain_memberships(user)
            user_adapter.update(user['_id'], {'user_domain_memberships': memberships})
