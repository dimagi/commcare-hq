from django.core.management.base import BaseCommand
from corehq.apps.users.models import CommCareUser
from corehq.apps.es import UserES
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from corehq.util.log import with_progress_bar
from dimagi.utils.couch.database import iter_docs


def get_affected_ids():
    users = (UserES()
             .mobile_users()
             .non_null("location_id")
             .fields(["location_id", "user_data.commcare_location_id", "_id",
                      "domain"])
             .run().hits)
    print "There are {} users".format(len(users))
    user_ids, location_ids = [], []
    for u in users:
        domain = Domain.get_by_name(u['domain'])
        user_data_loc_id = u.get('user_data', {}).get('commcare_location_id')
        loc_ids_dont_match = u['location_id'] != user_data_loc_id
        if loc_ids_dont_match and not domain.supports_multiple_locations_per_user:
            user_ids.append(u['_id'])
            location_ids.append(u['location_id'])
    print "There are {} bad users".format(len(user_ids))
    return user_ids, location_ids


def set_correct_locations():
    user_ids, location_ids = get_affected_ids()
    locations = {
        doc['_id']: Location.wrap(doc)
        for doc in iter_docs(Location.get_db(), set(location_ids))
    }
    users_set, users_unset = 0, 0
    all_users = iter_docs(CommCareUser.get_db(), user_ids)
    for doc in with_progress_bar(all_users, length=len(user_ids)):
        user = CommCareUser.wrap(doc)
        if user.location_id != user.user_data.get('commcare_location_id'):
            location = locations.get(user.location_id, None)
            try:
                if location:
                    user.set_location(location)
                    users_set += 1
                else:
                    user.unset_location()
                    users_unset += 1
            except Exception as e:
                print user._id, "failed", repr(e)
                location.save()
    print "Set locations on {} users".format(users_set)
    print "Unset locations on {} users".format(users_unset)


class Command(BaseCommand):
    help = "Deletes the given user"
    args = '<user>'

    def handle(self, *args, **options):
        set_correct_locations()
