from django.core.management.base import BaseCommand
from corehq.apps.locations.models import Location
from couchdbkit.exceptions import ResourceNotFound
from dimagi.utils.couch.database import iter_docs
from corehq.apps.users.models import CouchUser, CommCareUser


class Command(BaseCommand):
    help = ''

    def handle(self, *args, **options):
        self.stdout.write("...\n")

        relevant_ids = set([r['id'] for r in CouchUser.get_db().view(
            'users/by_username',
            reduce=False,
        ).all()])

        to_save = []

        for user_doc in iter_docs(CouchUser.get_db(), relevant_ids):
            if 'commtrack_location' in user_doc:
                user = CommCareUser.get(user_doc['_id'])

                try:
                    original_location_object = Location.get(user['commtrack_location'])
                except ResourceNotFound:
                    # if there was bad data in there before, we can ignore it
                    continue
                user.set_locations([original_location_object])

                del user_doc['commtrack_location']

                to_save.append(user_doc)

                if len(to_save) > 500:
                    CouchUser.get_db().bulk_save(to_save)
                    to_save = []

        if to_save:
            Location.get_db().bulk_save(to_save)
