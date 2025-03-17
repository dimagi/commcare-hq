# One-off migration, June 2024
from itertools import chain

from django.core.management.base import BaseCommand

from corehq.apps.domain_migration_flags.api import once_off_migration
from corehq.apps.users.models import CommCareUser
from corehq.dbaccessors.couchapps.all_docs import (
    get_doc_count_by_type,
    iter_all_doc_ids,
)
from corehq.util.couch import DocUpdate, iter_update
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Remove now-stale CouchUser.user_data field"

    def handle(self, *args, **options):
        do_migration()


@once_off_migration("rm_couch_user_data")
def do_migration():
    db = CommCareUser.get_db()
    count = (get_doc_count_by_type(db, 'WebUser')
             + get_doc_count_by_type(db, 'CommCareUser'))
    all_ids = chain(iter_all_doc_ids(db, 'WebUser'),
                    iter_all_doc_ids(db, 'CommCareUser'))
    iter_update(db, _update_user, with_progress_bar(all_ids, count), verbose=True)


def _update_user(user_doc):
    couch_data = user_doc.pop('user_data', ...)
    if couch_data is not ...:
        return DocUpdate(user_doc)
