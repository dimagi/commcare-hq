#OTA restore from pact
#recreate submissions to import as new cases to
from datetime import datetime
from gevent.pool import Pool
import simplejson

from django.core.management.base import NoArgsCommand
from corehq.apps.domain.models import Domain
import sys
from dimagi.utils.parsing import ISO_FORMAT
from localsettings import PACT_URL
from pact.management.commands import PactMigrateCommand
from pact.management.commands.constants import  POOL_SIZE
from pact.enums import PACT_DOMAIN
from casexml.apps.case.models import CommCareCase


class Command(PactMigrateCommand):
    help = "Apply the last schedules of pact patients onto the HQ case computed_ field"
    option_list = NoArgsCommand.option_list + (
    )


    def process_schedule(self, case_json):

        hqcase = CommCareCase.get(case_json['_id'])
#        print case_json['_id']
#        print case_json['weekly_schedule']

        if len(case_json.get('weekly_schedule', [])) > 0:
            print "updating schedule for %s" % case_json['_id']
            hqcase['computed_']['pact_weekly_schedule'] = case_json['weekly_schedule']
            hqcase['computed_modified_on'] = datetime.utcnow().strftime(ISO_FORMAT)
            hqcase.save()


    def handle(self, **options):
        domain_obj = Domain.get_by_name(PACT_DOMAIN)
        self.get_credentials()

        #get cases
        case_ids = simplejson.loads(self.get_url(PACT_URL + 'hqmigration/cases/'))
        pool = Pool(POOL_SIZE)

        for id in case_ids:
            try:
                case_json = simplejson.loads(self.get_url(PACT_URL + 'hqmigration/cases/%s' % id))
            except Exception, ex:
                print "@@@@@@@@@@@@ Error on case %s" % id
                #hard exit because we need to make sure this never fails
                sys.exit()
                #            self.process_case(case_json)
            pool.spawn(self.process_schedule, case_json)




