from optparse import make_option
from django.core.management.base import BaseCommand
import sys
from datetime import datetime, timedelta
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.es import CaseES
from corehq.apps.users.models import CommCareUser
from pact.api import submit_case_update_form
from pact.dot_data import filter_obs_for_day
from pact.enums import PACT_DOMAIN, REGIMEN_CHOICES, DOT_NONART, DOT_ART, PACT_REGIMEN_CHOICES
from pact.models import CObservation, PactPatientCase
from pact.regimen import regimen_dict_from_choice
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
    option_list = BaseCommand.option_list + (
        make_option('--correct',
                    action='store_true',
                    dest='correct',
                    default=False,
                    help='Correct problematic labels'),
    )

    def println(self, message):
        self.stdout.write("%s\n" % message)
    def handle(self, *args, **options):
        cases = CommCareCase.view('hqcase/types_by_domain', key=[PACT_DOMAIN, 'cc_path_client'], reduce=False).all()
        do_correct = options['correct']
        print options
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
                    self.println("Problem patient: %s" % (casedoc.pactid))
                    self.println("\tnonart: %s" % nonart)
                    self.println("\tart: %s" % art)

                    if do_correct:
                        self.println("Fixing regimens")

                        update_dict = {}
                        print casedoc.artregimen
                        print casedoc.nonartregimen
                        default_art_value = PACT_REGIMEN_CHOICES[int(casedoc.artregimen)][1][0][0]
                        default_nonart_value = PACT_REGIMEN_CHOICES[int(casedoc.nonartregimen)][1][0][0]

                        print default_nonart_value
                        print default_art_value

                        art_props = regimen_dict_from_choice(DOT_ART, default_art_value)
                        nonart_props = regimen_dict_from_choice(DOT_NONART, default_nonart_value)

                        print nonart_props
                        print art_props

                        update_dict.update(art_props)
                        update_dict.update(nonart_props)

                        pactimporter = CommCareUser.get_by_username('pactimporter@pact.commcarehq.org')
                        submit_case_update_form(casedoc, update_dict, pactimporter)

                else:
                    self.println("#### No pactid %s" % casedoc._id)
                if nonart.startswith('Error'):
                    self.println("\tNONART: %s" % REGIMEN_CHOICES[int(casedoc.nonartregimen)])

                if art.startswith('Error'):
                    self.println("\tART: %s" % REGIMEN_CHOICES[int(casedoc.artregimen)])
                #self.println('\tNONART: %s' % nonart)
                #self.println('\tART: %s' % art)











