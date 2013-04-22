from datetime import datetime, timedelta
import time
from dateutil.parser import parser
from django.core.cache import cache
from django.http import HttpResponse
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.es import FullXFormES
from pact.enums import PACT_DOMAIN
from pact.lib.quicksect import IntervalNode
from pact.utils import get_patient_display_cache

cached_schedules = {}

def get_seconds(d):
    return time.mktime(d.utctimetuple())


class CHWPatientSchedule(object):
    def __init__(self, username, intervaltrees, raw_schedule):
        self.username = username
        self.intervals = intervaltrees
        self.raw_schedule = raw_schedule

    def scheduled_for_date(self, date_val):
        """
        For a given date, return the array of pact_ids that are scheduled for visiting.  This will check the activate date by using the internal interval tree.
        Parameter:  datetime value
        Returns: array of pact_ids
        """
        #tree.intersect(get_seconds(time_check)-1, get_seconds(time_check), lambda x: res.append(x.other))
        day_of_week = date_val.isoweekday() % 7
        if not self.intervals.has_key(day_of_week):
            return []
        else:
            pass
        day_tree = self.intervals[day_of_week]
        results = []
        day_tree.intersect(get_seconds(date_val) - .1, get_seconds(date_val),
                           lambda x: results.append(x.other))
        return results


    @classmethod
    def get_schedule(cls, chw_username, override_date=None):
        """
        Generate schedule object for a given username
        """

        #cached_schedules = cache.get("%s_schedule" % (chw_username), None)
        cached_schedules = None

        if override_date == None:
            nowdate = datetime.now()
        else:
            nowdate = override_date

        day_intervaltree = {}
        if cached_schedules == None:
            #no documents, then we need to load them up
            db = CommCareCase.get_db()
            chw_schedules = db.view('pact/chw_dot_schedules', key=chw_username).all()
            to_cache = []
            for item in chw_schedules:
                single_sched = item['value']
                to_cache.append(single_sched)
            cache.set("%s_schedule" % (chw_username), simplejson.dumps(to_cache), 3600)
            cached_arr = to_cache
        else:
            cached_arr = simplejson.loads(cached_schedules)

        for single_sched in cached_arr:
            day_of_week = int(single_sched['day_of_week'])
            if day_intervaltree.has_key(day_of_week):
                daytree = day_intervaltree[day_of_week]
            else:
                #if there's no day of week indication for this, then it's just a null interval node.  To start this node, we make it REALLY old.
                daytree = IntervalNode(get_seconds(datetime.min),
                                       get_seconds(nowdate + timedelta(days=10)))
            if single_sched['ended_date'] == None:
                enddate = nowdate + timedelta(days=9)
            else:
                enddate = datetime.strptime(single_sched['ended_date'], "%Y-%m-%dT%H:%M:%SZ")

            startdate = datetime.strptime(single_sched['active_date'], "%Y-%m-%dT%H:%M:%SZ")
            case_id = single_sched['case_id']
            if single_sched.has_key('error'):
                print "Error, no pactid: %s" % single_sched['error']

            daytree.insert(get_seconds(startdate), get_seconds(enddate), other=case_id)
            day_intervaltree[day_of_week] = daytree
        return cls(chw_username, day_intervaltree, cached_arr)


def dots_submissions_by_case(case_id, query_date, username=None):
    """
    Actually run query for username submissions
    todo: do terms for the pact_ids instead of individual term?
    """
    xform_es = FullXFormES(PACT_DOMAIN)
    script_fields = {
        "doc_id": {"script": "_source._id"},
        "pact_id": {"script": "_source.form.pact_id", },
        "encounter_date": {"script": "_source.form.encounter_date", },
        "username": {"script": "_source.form.meta.username", },

        "visit_type": {"script": "_source.form.visit_type", },
        "visit_kept": {"script": "_source.form.visit_kept", },
        "contact_type": {"script": "_source.form.contact_type", },
        "observed_art": {"script": "_source.form.observed_art", },
        "observed_non_art": {"script": "_source.form.observed_non_art", },
        "observer_non_art_dose": {"script": "_source.form.observed_non_art_dose", },
        "observed_art_dose": {"script": "_source.form.observed_art_dose", },
        "pillbox_check": {"script": "_source.form.pillbox_check.check"},
        "scheduled": {"script": "_source.form.scheduled"}
    }

    term_block = {'form.#type': 'dots_form'}
    if username is not None:
        term_block['form.meta.username'] = username
    query = xform_es.by_case_id_query(PACT_DOMAIN, case_id, terms=term_block,
                                      date_field='form.encounter_date', startdate=query_date,
                                      enddate=query_date)
    query['sort'] = {'received_on': 'asc'}
    query['script_fields'] = script_fields
    query['size'] = 1
    query['from'] = 0
    res = xform_es.run_query(query)
    return res


def get_schedule_tally(username, total_interval, override_date=None):
    """
    Main entry point
    For a given username and interval, get a simple array of the username and scheduled visit (whether a submission is there or not)  exists.
    returns (schedule_tally_array, patient_array, total_scheduled (int), total_visited(int))
    schedul_tally_array = [visit_date, [(patient1, visit1), (patient2, visit2), (patient3, None), (patient4, visit4), ...]]
    where visit = XFormInstance
    """
    if override_date is None:
        nowdate = datetime.now()
        chw_schedule = CHWPatientSchedule.get_schedule(username)
    else:
        nowdate = override_date
        chw_schedule = CHWPatientSchedule.get_schedule(username, override_date=nowdate)

    patient_case_ids = set([x['case_id'] for x in chw_schedule.raw_schedule])
    patient_cache = get_patient_display_cache(list(patient_case_ids))

    #got the chw schedule
    #now let's walk through the date range, and get the scheduled CHWs per this date.visit_dates = []
    ret = [] #where it's going to be an array of tuples:
    #(date, scheduled[], submissions[] - that line up with the scheduled)

    total_scheduled = 0
    total_visited = 0

    for n in range(0, total_interval):
        td = timedelta(days=n)
        visit_date = nowdate - td
        scheduled_case_ids = chw_schedule.scheduled_for_date(visit_date)
        patient_case_ids = set(filter(lambda x: x is not None, scheduled_case_ids))
        dereferenced_patient_info = [patient_cache.get(x, {}) for x in patient_case_ids]
        visited = []

        #inefficient, but we need to get the patients in alpha order
        #patients = sorted(patients, key=lambda x: x.last_name)

        dp = parser()
        for case_id in patient_case_ids:
            total_scheduled += 1
            search_results = dots_submissions_by_case(case_id, visit_date, username=username)
            submissions = search_results['hits']['hits']
            if len(submissions) > 0:
                #print submissions[0]['fields']
                #calculate if pillbox checked


                pillbox_check_str = submissions[0]['fields']['pillbox_check']
                if len(pillbox_check_str) > 0:
                    pillbox_check_data = simplejson.loads(pillbox_check_str)
                    anchor_date = dp.parse(pillbox_check_data.get('anchor'))
                else:
                    pillbox_check_data = {}
                    anchor_date = datetime.min
                encounter_date = dp.parse(submissions[0]['fields']['encounter_date'])
                submissions[0]['fields']['has_pillbox_check'] = 'Yes' if anchor_date.date() == encounter_date.date() else 'No'

                visited.append(submissions[0]['fields'])
                total_visited += 1
            else:
                #ok, so no submission from this chw, let's see if there's ANY from anyone on this day.
                search_results = dots_submissions_by_case(case_id, visit_date)
                other_submissions = search_results['hits']['hits']
                if len(other_submissions) > 0:
                    visited.append(other_submissions[0]['fields'])
                    total_visited += 1
                else:
                    visited.append(None)
        ret.append((visit_date, zip(dereferenced_patient_info, visited)))
    return ret, patient_case_ids, total_scheduled, total_visited


def chw_calendar_submit_report(request, username):
    """Calendar view of submissions by CHW, overlaid with their scheduled visits, and whether they made them or not."""
    return_context = {}
    return_context['username'] = username
    total_interval = 7
    if 'interval' in request.GET:
        try:
            total_interval = int(request.GET['interval'])
        except ValueError:
            pass

    #secret date ranges
    if 'enddate' in request.GET:
        end_date_str = request.GET.get('enddate', datetime.utcnow().strftime('%Y-%m-%d'))
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        end_date = datetime.utcnow()

    if 'startdate' in request.GET:
        #if there's a startdate, trump interval
        start_date_str = request.GET.get('startdate', datetime.utcnow().strftime('%Y-%m-%d'))
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        total_interval = (end_date - start_date).days


    ret, patients, total_scheduled, total_visited = get_schedule_tally(username,
                                                                       total_interval,
                                                                       override_date=end_date)

    if len(ret) > 0:
        return_context['date_arr'] = ret
        return_context['total_scheduled'] = total_scheduled
        return_context['total_visited'] = total_visited
        return_context['start_date'] = ret[0][0]
        return_context['end_date'] = ret[-1][0]
    else:
        return_context['total_scheduled'] = 0
        return_context['total_visited'] = 0

    return return_context
