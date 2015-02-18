from django.core.management.base import BaseCommand
from dimagi.utils.couch.database import iter_docs
from corehq.apps.users.models import CouchUser, CommCareUser


class Command(BaseCommand):
    help = ''

    def handle(self, *args, **options):
        self.stdout.write("Population location_id field...\n")

        relevant_ids = set([r['id'] for r in CouchUser.get_db().view(
            'users/by_username',
            reduce=False,
        ).all()])

        to_save = []

        for user_doc in iter_docs(CommCareUser.get_db(), relevant_ids):
            if user_doc['doc_type'] == 'WebUser':
                continue

            user = CommCareUser.get(user_doc['_id'])

            if user._locations:
                user_doc['location_id'] = user._locations[0]._id
                to_save.append(user_doc)

            if len(to_save) > 500:
                CouchUser.get_db().bulk_save(to_save)
                to_save = []

        if to_save:
            CouchUser.get_db().bulk_save(to_save)
