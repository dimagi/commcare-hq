import logging

from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation
from custom.enikshay.private_sector_datamigration.models import UserDetail

logger = logging.getLogger('private_sector_datamigration')


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        for loc in SQLLocation.active_objects.filter(
            domain=domain,
            location_type__code__in=['pac', 'pcc', 'pcp', 'plc'],
        ):
            location_id = loc.location_id
            logging.info('processing location %s' % location_id)
            agency_id = loc.metadata.get('private_sector_agency_id')
            if agency_id:
                user_detail = UserDetail.objects.get(agencyId=int(agency_id), isPrimary=True)
                uatbc_tu_id = user_detail.tuId or ''
                loc.metadata['uatbc_tu_id'] = uatbc_tu_id
                loc.save()
                logging.info('saved uatbc_tu_id \'%s\' to location %s' % (uatbc_tu_id, location_id))
            else:
                logging.info('skipping location %s' % location_id)

