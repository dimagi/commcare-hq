from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
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

        total_to_process = locs_matching_type.count()

        for i, loc in enumerate(locs_matching_type):
            private_sector_agency_id = loc.metadata.get('private_sector_agency_id', '')
            if not private_sector_agency_id.isdigit():
                continue
            agency_id = int(private_sector_agency_id)
            try:
                agency = Agency.objects.get(agencyId=agency_id)
            except Agency.DoesNotExist:
                continue
            loc.name = "%s - %d" % (agency.agencyName, agency_id)
            loc.save()
            try:
                user_detail = UserDetail.objects.get(agencyId=agency_id, isPrimary=True)
            except UserDetail.DoesNotExist:
                user_detail = None
            location_user = CommCareUser.get_by_user_id(loc.user_id)

            if user_detail is None or user_detail.firstName in ['dummy', 'DUMMY', 'Not Available']:
                agency_name_split = agency.agencyName.split()
                if len(agency_name_split) == 1:
                    location_user.first_name = agency_name_split[0]
                    location_user.last_name = ''
                else:
                    location_user.first_name = ' '.join(agency_name_split[:-1])
                    location_user.last_name = agency_name_split[-1]
            else:
                location_user.first_name = user_detail.firstName
                location_user.last_name = user_detail.lastName
            location_user.save()
            print 'processed agency %d, %d of %d' % (agency_id, i, total_to_process)
