from django.core.management import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.util.log import with_progress_bar
from custom.enikshay.models import AgencyIdCounter
from custom.enikshay.private_sector_datamigration.models import UserDetail, Agency


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--dry_run',
            action='store_true',
            default=False,
            dest='dry_run',
        )

    def handle(self, domain, dry_run=True, **options):
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

        location_ids_updated = []

        for i, loc in enumerate(with_progress_bar(locs_matching_type)):
            private_sector_agency_id = loc.metadata.get('private_sector_agency_id', '')
            if not private_sector_agency_id.isdigit():
                if dry_run:
                    print 'assign private_sector_agency_id to %s' % loc.name
                    continue
                else:
                    loc.metadata['private_sector_agency_id'] = private_sector_agency_id = str(AgencyIdCounter.get_new_agency_id())
                    loc.save()
            agency_name_split = loc.name.split('-')
            if agency_name_split[-1].strip() != private_sector_agency_id:
                print 'old name: %s' % loc.name
                loc.name = '%s - %s' % (loc.name, private_sector_agency_id)
                if not dry_run:
                    loc.save()
                print 'new name: %s' % loc.name
                print 'updated loc %s' % loc.location_id
                print '-----'
                location_ids_updated.append(loc.location_id)

        print "Updated {} users".format(len(location_ids_updated))
