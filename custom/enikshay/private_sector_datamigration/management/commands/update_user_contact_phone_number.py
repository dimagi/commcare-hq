from __future__ import absolute_import
from __future__ import print_function
from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.util.log import with_progress_bar
from custom.enikshay.private_sector_datamigration.models import UserDetail


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('location_ids', nargs='*')

    def handle(self, domain, location_ids, **options):
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
        if location_ids:
            locs_matching_type = locs_matching_type.filter(location_id__in=location_ids)

        count = 0

        for _, loc in enumerate(with_progress_bar(locs_matching_type)):
            private_sector_agency_id = loc.metadata.get('private_sector_agency_id', '')
            if not private_sector_agency_id.isdigit():
                continue
            agency_id = int(private_sector_agency_id)

            try:
                user_detail = UserDetail.objects.get(agencyId=agency_id, isPrimary=True)
            except UserDetail.DoesNotExist:
                continue

            location_user = CommCareUser.get_by_user_id(loc.user_id)

            contact_phone_number = location_user.user_data.get('contact_phone_number')
            if not contact_phone_number and len(user_detail.mobileNumber) == 10:
                location_user.user_data['contact_phone_number'] = '91' + user_detail.mobileNumber
                location_user.save()
                print('Updated %s' % location_user.user_id)
                count += 1

        print('%d users updated.' % count)
