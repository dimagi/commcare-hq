from optparse import make_option
from django.core.management.base import BaseCommand
import sys
from datetime import datetime, timedelta
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.es import CaseES
from pact.dot_data import filter_obs_for_day
from pact.enums import PACT_DOMAIN, REGIMEN_CHOICES
from pact.models import CObservation, PactPatientCase
from pact.reports.dot_calendar import  DOTCalendarReporter


copy_keys = ['note', 'day_index', 'day_slot', 'dose_number', 'total_doses', 'method','adherence', 'encounter_date']
class CustomEncoder(simplejson.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, CObservation):
#            return obj.to_json()
            raw = obj.to_json()
            ret = {}
            for k in copy_keys:
                ret[k] = raw[k]
            return ret
#            return raw
        return simplejson.JSONEncoder.default(self, obj)

class Command(BaseCommand):
    args = 'id'
    help = 'Verify regimen frequencies are OK on migrated patients'
    option_list = BaseCommand.option_list + ( )

    def println(self, message):
        self.stdout.write("%s\n" % message)
    def handle(self, *args, **options):
        cases = CommCareCase.view('hqcase/types_by_domain', key=[PACT_DOMAIN, 'cc_path_client'], reduce=False).all()
        for v in cases:
#            print v
            casedoc = PactPatientCase.get(v['id'])
            has_error=False


            try:
                nonart = "\tNONART: %s" % casedoc.nonart_regimen_label_string_display()
            except Exception, ex:
                has_error=True
                nonart = "%s" % ex

            try:
                art = "\tART: %s" % casedoc.art_regimen_label_string_display()
            except Exception, ex:
                art = "%s" % ex
                has_error=True


            if has_error:
                if hasattr(casedoc, 'pactid'):
                    #self.println("#### Patient %s %s" % (casedoc.pactid, casedoc._id))
                    self.println("%s" % (casedoc.pactid))
                else:
                    self.println("#### No pactid %s" % casedoc._id)
                if nonart.startswith('Error'):
                    self.println("\tNONART: %s" % REGIMEN_CHOICES[int(casedoc.nonartregimen)])

                if art.startswith('Error'):
                    self.println("\tART: %s" % REGIMEN_CHOICES[int(casedoc.artregimen)])
                #self.println('\tNONART: %s' % nonart)
                #self.println('\tART: %s' % art)











