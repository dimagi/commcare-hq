from __future__ import absolute_import
from __future__ import print_function
from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.util.log import with_progress_bar
from custom.enikshay.private_sector_datamigration.models import UserDetail, Agency


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        locs_matching_type = SQLLocation.active_objects.filter(
            domain=domain,
            location_type__code__in=[
                'pac',
                'pcp',
                'plc',
                'fo',
                'pcc',
            ],
        )

        user_ids_updated = []

        for i, loc in enumerate(with_progress_bar(locs_matching_type)):
            private_sector_agency_id = loc.metadata.get('private_sector_agency_id', '')
            if not private_sector_agency_id.isdigit():
                continue
            agency_id = int(private_sector_agency_id)

            try:
                agency = Agency.objects.get(agencyId=agency_id)
            except Agency.DoesNotExist:
                continue

            try:
                user_detail = UserDetail.objects.get(agencyId=agency_id, isPrimary=True)
            except UserDetail.DoesNotExist:
                user_detail = None
            location_user = CommCareUser.get_by_user_id(loc.user_id)

            if user_detail is None or user_detail.firstName.lower() in ['dummy', 'not available', 'na']:
                agency_name_split = agency.agencyName.split()
                if len(agency_name_split) == 1:
                    location_user.first_name = agency_name_split[0]
                    location_user.last_name = ''
                else:
                    location_user.first_name = ' '.join(agency_name_split[:-1])
                    location_user.last_name = agency_name_split[-1]
                location_user.save()
                user_ids_updated.append(location_user._id)

        print(user_ids_updated)
        print("Updated {} users".format(len(user_ids_updated)))
