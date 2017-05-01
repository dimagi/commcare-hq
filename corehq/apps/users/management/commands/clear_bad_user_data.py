from django.core.management.base import BaseCommand
from corehq.apps.es import UserES
from corehq.apps.users.models import CommCareUser
from corehq.util.couch import iter_update, DocUpdate
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = ("Clears commcare_location_id and commtrack-supply-point on any "
            "users without location_id set")

    def handle(self, **options):
        clean_users()


def get_bad_user_ids():
    res = (UserES()
           .mobile_users()
           .empty("location_id")
           .fields(["_id", "domain", "username", "user_data.commcare_location_id"])
           .run().hits)
    return [u['_id'] for u in res
            if u.get('user_data', {}).get('commcare_location_id')
            or u.get('user_data', {}).get('commtrack-supply-point')]


def clean_user(doc):
    """Take any users with no location_id and clear the location user_data"""
    if doc['location_id']:
        return

    had_bad_data = any([
        doc.get('user_data', {}).pop('commcare_location_id', False),
        doc.get('user_data', {}).pop('commtrack-supply-point', False),
    ])
    if had_bad_data:
        return DocUpdate(doc)


def clean_users():
    all_ids = with_progress_bar(get_bad_user_ids())
    iter_update(CommCareUser.get_db(), clean_user, all_ids, verbose=True)
