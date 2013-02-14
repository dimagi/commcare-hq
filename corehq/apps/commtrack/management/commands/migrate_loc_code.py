from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from casexml.apps.case.models import CommCareCase
import sys

class Command(BaseCommand):
    args = 'domain'
#    option_list = BaseCommand.option_list + (
#         )
    help = 'Migrate commtrack locations created before the schema for sms code was changed'

    def handle(self, *args, **options):
        try:
            domain = args[0]
        except IndexError:
            self.stderr.write('domain required\n')
            return

        self.stdout.write('Migrating...\n')

        supply_point_cases = CommCareCase.get_db().view(
            'commtrack/supply_point_by_loc',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        )

        for result in supply_point_cases:
            loc_id = result['key'][-1]
            loc = Location.get(loc_id)
            case = result['doc']

            old_code = case.get('site_code', '')
            new_code = getattr(loc, 'site_code', '')

            if old_code and not new_code:
                loc.site_code = old_code
                loc.save()
                self.stdout.write('migrated %s (%s)\n' % (loc.name, loc.site_code))
