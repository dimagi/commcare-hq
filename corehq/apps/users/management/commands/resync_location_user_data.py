from corehq.apps.locations.models import Location
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch.database import iter_docs
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    args = "domain"
    help = "Re-syncs location user data for all mobile workers in the domain."

    def process_user(self, user):
        if user.location_id:
            user.set_location(Location.get(user.location_id))
        else:
            user.unset_location()

    def handle(self, *args, **options):
        if len(args) == 0:
            raise CommandError("Usage: python manage.py resync_location_user_data %s" % self.args)

        domain = args[0]
        ids = (
            CommCareUser.ids_by_domain(domain, is_active=True) +
            CommCareUser.ids_by_domain(domain, is_active=False)
        )
        for doc in iter_docs(CommCareUser.get_db(), ids):
            user = CommCareUser.wrap(doc)
            try:
                self.process_user(user)
            except Exception as e:
                print "Error processing user %s: %s" % (user._id, e)
