import logging

from django.core.management.base import BaseCommand

from corehq.apps.es import UserES, users as user_filters
from corehq.apps.users.models import CouchUser
from corehq.util.couch import iter_update, DocUpdate
from corehq.util.log import with_progress_bar


logger = logging.getLogger('user_migration')
logger.setLevel('DEBUG')


class Command(BaseCommand):
    args = ""
    help = ("(Migration) Autofill the new field assigned_location_ids to existing users")

    def handle(self, *args, **options):
        self.options = options
        user_ids = with_progress_bar(self.get_user_ids())
        logger.info('migrating {} users'.format(len(user_ids)))
        iter_update(CouchUser.get_db(), self._migrate_user, user_ids, verbose=True)
        logger.info('done')

    def _migrate_user(self, doc):
        if not doc['location_id']:
            return

        doc['assigned_location_ids'] = [doc['location_id']]
        doc['user_data'].update({
            'commcare_location_ids': doc['location_id']
        })
        return DocUpdate(doc)

    def get_user_ids(self):
        res = (UserES()
               .OR(user_filters.web_users(), user_filters.mobile_users())
               .non_null('location_id')
               .exclude_source()
               .run())
        return res.doc_ids
