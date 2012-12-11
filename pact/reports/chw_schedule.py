from datetime import datetime, timedelta, timedelta
import time
from django.core.cache import cache
from django.http import HttpResponse
import simplejson
from casexml.apps.case.models import CommCareCase
from corehq.apps.api.es import XFormES
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
        #print "create for username %s" % (username)

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
            #print 'has key for this day of the week %d' % (day_of_week)
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
        print "chw_username: %s" % chw_username

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
            #cached_schedules[chw_username] = CHWPatientSchedule(chw_username, day_intervaltree, chw_schedules)
        return cls(chw_username, day_intervaltree, cached_arr)




def query_submissions(username):
    xform_es = XFormES()
    query = xform_es.base_query(PACT_DOMAIN, start=0, size=25)
    query['fields'] = [
        "form.#type",
        "form.encounter_date",
        "form.note.encounter_date",
        "form.case.case_id",
        "form.case.@case_id",
        "form.pact_id",
        "form.note.pact_id",
        "received_on",
        "form.meta.timeStart",
        "form.meta.timeEnd"
    ]
    query['filter']['and'].append({"term": {"form.meta.username": username}})
    return xform_es.run_query(query)


def username_submissions(username, query_date, case_id=None):
    """
    Actually run query for username submissions
    todo: do terms for the pact_ids instead of individual term?
    """
    xform_es = XFormES()
    query = {
#        "fields": [
#            "_id",
#            "received_on",
#            "form.pact_id",
#            "form.encounter_date"
#            "form.meta.username"
#        ],
        "script_fields" : {
            "doc_id" : {
                "script" : "_source._id"
            },
            "pact_id": {
                "script": "_source.form.pact_id",
            },
            "encounter_date": {
                "script": "_source.form.encounter_date",
                },

            "username": {
                "script": "_source.form.meta.username",
                },

        },
        "query": {
            "filtered": {
                "filter": {
                    "and": [
                        {
                            "term": {
                                "domain": "pact"
                            }
                        },
                        {
                            "term": {
                                "form.meta.username": username
                            }
                        },
                        {
                            "numeric_range": {
                                "form.encounter_date": {
                                    "gte": query_date.strftime("%Y-%m-%d"),
                                    "lte": query_date.strftime("%Y-%m-%d")
                                }
                            }
                        }
                    ]
                }
            }
        },
        "sort": {
            "received_on": "asc"
        },
        "size": 1,
        "from": 0
    }

    if case_id is not None:
        query['query']['filtered']["query"] = {
                "query_string": {
                    "query": "(form.case.case_id:%(case_id)s OR form.case.@case_id:%(case_id)s)" % dict(case_id=case_id)
                }
            }
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
    xform_ex = XFormES()
    if override_date == None:
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



        for case_id in patient_case_ids:
            total_scheduled+=1
            #            searchkey = [str(username), str(pact_id), visit_date.year, visit_date.month, visit_date.day]
            search_results = username_submissions(username, visit_date, case_id=case_id)
            submissions = search_results['hits']['hits']
#            print "\tquerying submissions: %s: %s" % (username, visit_date)
            #            submissions = XFormInstance.view('dotsview/dots_submits_by_chw_per_patient_date', key=searchkey, include_docs=True).all()
            #            submissions = []
            #ES Query
            if len(submissions) > 0:
                print submissions
                visited.append(submissions[0]['fields'])
                total_visited += 1
            else:
            #ok, so no submission from this chw, let's see if there's ANY from anyone on this day.
            #                other_submissions = XFormInstance.view('pactcarehq/all_submits_by_patient_date', key=[str(pact_id), visit_date.year, visit_date.month, visit_date.day, 'http://dev.commcarehq.org/pact/dots_form' ], include_docs=True).all()
                other_submissions = []
                if len(other_submissions) > 0:
                    visited.append(other_submissions[0])
                    total_visited += 1
                else:
                    visited.append(None)
        ret.append((visit_date, zip(dereferenced_patient_info, visited)))
    return ret, patient_case_ids, total_scheduled, total_visited


def chw_calendar_submit_report(request, username):
    """Calendar view of submissions by CHW, overlaid with their scheduled visits, and whether they made them or not."""
    return_context = {}
    all_patients = request.GET.get("all_patients", False)
    return_context['username'] = username
    user = request.user
    total_interval = 30
    if request.GET.has_key('interval'):
        try:
            total_interval = int(request.GET['interval'])
        except:
            pass

    ret, patients, total_scheduled, total_visited = get_schedule_tally(username, total_interval)
    nowdate = datetime.now()

    return_context['date_arr'] = ret
    return_context['total_scheduled'] = total_scheduled
    return_context['total_visited'] = total_visited
    return_context['start_date'] = ret[0][0]
    return_context['end_date'] = ret[-1][0]

    if request.GET.get('getcsv', None) != None:
        csvdata = []
        csvdata.append(','.join(
            ['visit_date', 'assigned_chw', 'pact_id', 'is_scheduled', 'contact_type', 'visit_type',
             'visit_kept', 'submitted_by', 'visit_id']))
        for date, pt_visit in ret:
            if len(pt_visit) > 0:
                for cpt, v in pt_visit:
                    rowdata = [date.strftime('%Y-%m-%d'), username, cpt.pact_id]
                    if v != None:
                        #is scheduled
                        if v.form['scheduled'] == 'yes':
                            rowdata.append('scheduled')
                        else:
                            rowdata.append('unscheduled')
                            #contact_type
                        rowdata.append(v.form['contact_type'])

                        #visit type
                        rowdata.append(v.form['visit_type'])

                        #visit kept
                        rowdata.append(v.form['visit_kept'])

                        rowdata.append(v.form['meta']['username'])
                        if v.form['meta']['username'] == username:
                            rowdata.append('assigned')
                        else:
                            rowdata.append('covered')
                        rowdata.append(v.get_id)
                    else:
                        rowdata.append('novisit')
                    csvdata.append(','.join(rowdata))
            else:
                csvdata.append(','.join([date.strftime('%Y-%m-%d'), 'nopatients']))

        resp = HttpResponse()

        resp['Content-Disposition'] = 'attachment; filename=chw_schedule_%s-%s_to_%s.csv' % (
            username, datetime.now().strftime("%Y-%m-%d"),
            (nowdate - timedelta(days=total_interval)).strftime("%Y-%m-%d"))
        resp.write('\n'.join(csvdata))
        return resp

    else:
        return return_context
