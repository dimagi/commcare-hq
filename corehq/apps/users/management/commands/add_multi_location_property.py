from django.core.management.base import BaseCommand

from corehq.apps.es import UserES, users as user_filters
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import user_location_data
from corehq.util.couch import iter_update, DocUpdate
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    args = ""
    help = ("(Migration) Autofill the new field assigned_location_ids to existing users")

    def handle(self, *args, **options):
        self.options = options
        user_ids = with_progress_bar(self.get_user_ids())
        iter_update(CouchUser.get_db(), self.migrate_user, user_ids, verbose=True)

    def migrate_user(self, doc):
        if doc['doc_type'] == 'WebUser':
            return self.migrate_web_user(doc)
        elif doc['doc_type'] == 'CommCareUser':
            return self.migrate_cc_user(doc)

    def migrate_cc_user(self, doc):

        if is_already_migrated(doc):
            return

        apply_migration(doc)
        apply_migration(doc['domain_membership'])
        doc['user_data'].update({
            'commcare_location_ids': user_location_data(doc['assigned_location_ids'])
        })
        return DocUpdate(doc)

    def migrate_web_user(self, doc):
        if all([is_already_migrated(dm) for dm in doc['domain_memberships']]):
            return

        for membership in doc['domain_memberships']:
            if not is_already_migrated(membership):
                apply_migration(membership)

        return DocUpdate(doc)

    def get_user_ids(self):
        res = (UserES()
               .OR(user_filters.web_users(), user_filters.mobile_users())
               .non_null('location_id')
               .non_null('domain_memberships.location_id')
               .exclude_source()
               .run())
        return list(res.doc_ids)


def is_already_migrated(doc):
    # doc can be a user dict or a domain_membership dict
    return ('assigned_location_ids' in doc and
            doc['location_id'] in doc['assigned_location_ids'] and
            'commcare_location_ids' in doc['user_data'] and
            doc['user_data']['commcare_location_ids'] == user_location_data('assigned_location_ids'))


def apply_migration(doc):
    # doc can be a user dict or a domain_membership dict
    if doc['location_id']:
        if 'assigned_location_ids' in doc:
            doc['assigned_location_ids'].append(doc['location_id'])
        else:
            doc['assigned_location_ids'] = [doc['location_id']]
    else:
        if 'assigned_location_ids' not in doc:
            doc['assigned_location_ids'] = []
