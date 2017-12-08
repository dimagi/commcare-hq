from __future__ import print_function

from datetime import date
from django.core.management import BaseCommand

from corehq.apps.es import UserES
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import CommCareUser


def looks_archiveable(user):
    return (
        user.created_on.date() == date(2017, 11, 6)
        and user.user_data.get('contact_phone_number') is None
        and user._get_form_ids() == 0
    )


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        field_officer_location_type = LocationType.objects.get(domain=domain, code='fo')
        for field_officer_location in SQLLocation.active_objects.filter(
            domain=domain,
            location_type=field_officer_location_type,
        ):
            user_query = UserES().domain(domain).mobile_users().location(
                field_officer_location.location_id
            ).fields(['_id'])
            user_ids = [u['_id'] for u in user_query.run().hits]
            # print('user_ids with %s: %s' % (field_officer_location.location_id, user_ids))
            users = map(CommCareUser.get, user_ids)
            archiveable_users = [u for u in users if looks_archiveable(u)]
            nonarchiveable_users = [u for u in users if not looks_archiveable(u)]
            if len(nonarchiveable_users) == 1:
                continue
                for archiveable_user in archiveable_users:
                    archiveable_user.is_active = False
                    # archiveable_user.save()
                    print('archived %s' % archiveable_user._id)
                field_officer_location.user_id = nonarchiveable_users[0]._id
                # field_officer_location.save()
                print('set location user to: %s' % nonarchiveable_users[0]._id)
            else:
                print('multiple nonarchiveable users for %: %' % (field_officer_location.location_id, user_ids))

