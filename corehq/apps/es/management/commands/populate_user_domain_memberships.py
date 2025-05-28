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
    common_dm = 'user_domain_memberships'
    mobile_dm = 'domain_membership'
    web_dm = 'domain_memberships'

    query_set = UserES().show_inactive()

    for user in with_progress_bar(query_set.scroll_ids_to_disk_and_iter_docs(), query_set.count()):
        update_common_dm = False
        if common_dm not in user:
            update_common_dm = True
        elif common_dm in user and mobile_dm in user and [user[mobile_dm]] != user[common_dm]:
            update_common_dm = True
        elif common_dm in user and web_dm in user and user[web_dm] != user[common_dm]:
            update_common_dm = True
        if update_common_dm:
            memberships = get_user_domain_memberships(user)
            user_adapter.update(
                user['_id'],
                {common_dm: memberships},
                refresh=True
            )
