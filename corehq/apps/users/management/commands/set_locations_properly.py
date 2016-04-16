from django.core.management.base import BaseCommand
from corehq.apps.users.models import CommCareUser
from corehq.apps.es import UserES
from corehq.apps.locations.models import Location
from dimagi.utils.couch.database import iter_docs


def get_affected_ids():
    users = (UserES()
             .mobile_users()
             .non_null("location_id")
             .fields(["location_id", "user_data.commcare_location_id", "_id"])
             .run().hits)
    print "There are {} users".format(len(users))
    user_ids, location_ids = [], []
    for u in users:
        if u['location_id'] != u.get('user_data', {}).get('commcare_location_id'):
            user_ids.append(u['_id'])
            location_ids.append(u['location_id'])
    print "There are {} bad users".format(len(user_ids))
    return user_ids, location_ids


def set_correct_locations():
    user_ids, location_ids = get_affected_ids()
    locations = {
        doc['_id']: Location.wrap(doc)
        for doc in iter_docs(Location.get_db(), location_ids)
    }
    users_set, users_unset = 0, 0
    for doc in iter_docs(CommCareUser.get_db(), user_ids):
        user = CommCareUser.wrap(doc)
        if user.location_id != user.user_data.get('commcare_location_id'):
            location = locations.get(user.location_id, None)
            if location:
                user.set_location(location)
                users_set += 1
            else:
                user.unset_location()
                users_unset += 1
    print "Set locations on {} users".format(users_set)
    print "Unset locations on {} users".format(users_unset)


class Command(BaseCommand):
    help = "Deletes the given user"
    args = '<user>'

    def handle(self, *args, **options):
        set_correct_locations()
