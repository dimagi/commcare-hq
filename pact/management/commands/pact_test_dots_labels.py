from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
import sys
from datetime import datetime, timedelta
from django.utils.safestring import mark_safe
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.es import CaseES
from pact.enums import PACT_DOMAIN
from pact.models import CObservation
from pact.reports.dot_calendar import DOTCalendar, DOTCalendarReporter, obs_for_day, merge_dot_day


import simplejson
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
    help = 'Closes the specified poll for voting'
    option_list = BaseCommand.option_list + (
        make_option('--idtype',
                    action='store',
                    dest='id_type',
                    default="pact_id",
                    help='ID type: pact_id or case_id'),

        make_option('--anchor',
                    action='store',
                    dest='anchor_date',
                    default=datetime.utcnow().date().strftime('%Y-%m-%d'),
                    help='anchor_date - default to today'),
        make_option('--days',
                    action='store',
                    dest='days',
                    default=10,
                    help='DOT encounter_date interval to cover - 10 days'),
        )

    def println(self, message):
        self.stdout.write("%s\n" % message)
    def handle(self, *args, **options):
        #case = CommCareCase.get(args[0])
        id_type = options['id_type']
        id = args[0]

        anchor_date_str = options['anchor_date']

        #watch for tz date boundaries
        anchor_date = datetime.strptime(anchor_date_str, '%Y-%m-%d')
        days = int(options['days'])

        start_date = anchor_date - timedelta(days=days)


        self.stdout.write("Anchor date query: %s\n" % anchor_date)
        self.stdout.write("Day Query: %s\n" % days)
        if len(args) == 0:
            self.stderr.write("Enter an id")
            sys.exit()
        else:
            case_es = CaseES()

            q = case_es.base_query(PACT_DOMAIN)
            if id_type == "pact_id":
                term = "pactid"

            else:
                term = "_id"
            q['filter']['and'].append({"term": {term: id}})
            q['fields'] = ['_id', 'pactid', 'name']
            qres = case_es.run_query(q)

            self.println(qres['hits']['hits'][0])
            case_id = qres['hits']['hits'][0]['fields']['_id']
            casedoc = CommCareCase.get(case_id)

            dcal = DOTCalendarReporter(casedoc, start_date=start_date, end_date=anchor_date)
            for d in range((anchor_date-start_date).days):
                odate = start_date + timedelta(days=d)
                day_obs = obs_for_day(odate.date(), dcal.dot_observation_range())
                print len(day_obs)

                merged = merge_dot_day(day_obs)
#                print merged
                print simplejson.dumps(merged, indent=4, cls=CustomEncoder)


#            for cal in dcal.calendars:
#                print cal
#                print mark_safe(cal)






