from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from custom.enikshay.private_sector_datamigration.models import UserDetail


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        for loc in SQLLocation.active_objects.filter(
            domain=domain,
            location_type__code__in=[
                'pac',
                'pcp',
                'plc',
                'ps-fieldstaff',
            ],
        ):
            private_sector_agency_id = loc.metadata.get('private_sector_agency_id', '')
            if not private_sector_agency_id.isdigit():
                continue
            agency_id = int(private_sector_agency_id)
            try:
                user_detail = UserDetail.objects.get(agencyId=agency_id)
            except UserDetail.DoesNotExist:
                continue
            location_user = CommCareUser.get_by_user_id(loc.user_id)
            location_user.first_name = user_detail.firstName
            location_user.last_name = user_detail.lastName
            location_user.save()
            split_loc_name = loc.name.split(' - ')
            if len(split_loc_name) == 2 and split_loc_name[1] == private_sector_agency_id:
                loc.name = split_loc_name[0]
                loc.save()
            print 'processed agency %d' % agency_id
