from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import Location
from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.loosechange import map_reduce
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

        self.println('Migrating...')

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
                self.println('migrated %s (%s)' % (loc.name, loc.site_code))

        self.println('Verifying code uniqueness...')

        all_codes = Location.get_db().view('commtrack/locations_by_code',
                                           startkey=[domain], endkey=[domain, {}])
        locs_by_code = map_reduce(lambda e: [(e['key'][-1].lower(), e['id'])], data=all_codes)
        for code, loc_ids in locs_by_code.iteritems():
            if len(loc_ids) == 1:
                continue

            self.println('duplicate code [%s]' % code)
            locs = Location.view('_all_docs', keys=loc_ids, include_docs=True)
            for loc in locs:
                self.println('  %s [%s]' % (loc.name, loc._id))

    def println(self, msg):
        self.stdout.write(msg + '\n')
