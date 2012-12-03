from bihar.reports.indicators.filters import A_MONTH, is_pregnant_mother, get_add, get_edd
from datetime import datetime, timedelta
from bihar.reports.indicators.visits import visit_is
from couchforms.models import XFormInstance
from couchforms.safe_index import safe_index
from dimagi.utils.parsing import string_to_datetime

EMPTY = (0,0)
GRACE_PERIOD = timedelta(days=7)


def _done_due(done, due):
    return "%s/%s" % (done, due)

def _in_last_month(date):
    today = datetime.today().date()
    return today - A_MONTH < date < today

def _in_timeframe(date, days):
    today = datetime.today().date()
    return today - timedelta(days=days) < date < today

def _mother_due_in_window(case, days):
    get_visitduedate = lambda case: case.edd - timedelta(days=days) + GRACE_PERIOD
    return is_pregnant_mother(case) and get_edd(case) and _in_last_month(get_visitduedate(case))
        
def _mother_delivered_in_window(case, days):
    get_visitduedate = lambda case: case.add + timedelta(days=days) + GRACE_PERIOD
    return is_pregnant_mother(case) and get_add(case) and _in_last_month(get_visitduedate(case))
        
def _done_due_count(cases, done_func, due_func):
    done = due = 0
    for case in cases:
        due_diff = due_func(case)
        if due_diff:
            due += due_diff
            done_diff = done_func(case)
            assert done_diff <= due_diff
            # this is to prevent the numerator from ever passing the denominator
            # though is probably not totally accurate
            done += done_diff
    return _done_due(done, due)

def _visits_due(case, schedule):
    return [i + 1 for i, days in enumerate(schedule) \
            if _mother_delivered_in_window(case, days)]

def _visits_done(case, schedule, type):
    due = _visits_due(case, schedule)
    count = len(filter(lambda a: visit_is(a, type), case.actions))
    return len([v for v in due if count > v])

def _delivered_in_timeframe(case, days):
    return is_pregnant_mother(case) and get_add(case) and _in_timeframe(case.add)

def _delivered_at_in_timeframe(case, at, days):
    return _delivered_in_timeframe(case, days) and getattr(case, 'birth_place', None) == at

def _get_time_of_visit_after_birth(case):
    for action in case.actions:
        if action.updated_unknown_properties.get("add", None):
            return action.date
    return None

def _visited_in_timeframe_of_birth(case, days):
    visit_time = _get_time_of_visit_after_birth(case)
    add = get_add(case)
    if visit_time and add:
        return add < visit_time < add + timedelta(days=days)
    return False



    
# NOTE: cases in, values out might not be the right API
# but it's what we need for the first set of stuff.
# might want to revisit.

# NOTE: this is going to be slooooow
def bp2_last_month(cases):
    due = lambda case: 1 if _mother_due_in_window(case, 75) else 0
    # make sure they've done 2 bp visits
    done = lambda case: 1 if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= 2 else 0
    return _done_due_count(cases, due, done)    
    
def bp3_last_month(cases):
    due = lambda case: 1 if _mother_due_in_window(case, 45) else 0
    # make sure they've done 2 bp visits
    done = lambda case: 1 if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= 3 else 0
    return _done_due_count(cases, due, done)    
    
def pnc_last_month(cases):
    pnc_schedule = (1, 3, 6)
    due = lambda case: len(_visits_due(case, pnc_schedule))
    done = lambda case: _visits_done(case, pnc_schedule, "pnc")
    return _done_due_count(cases, done, due)

def eb_last_month(cases):
    eb_schedule = (14, 28, 60, 90, 120, 150)
    due = lambda case: len(_visits_due(case, eb_schedule))
    done = lambda case: _visits_done(case, eb_schedule, "eb")
    return _done_due_count(cases, done, due)

def cf_last_month(cases):
    cf_schedule_in_months = (6, 7, 8, 9, 12, 15, 18)
    cf_schedule = (m * 30 for m in cf_schedule_in_months)
    due = lambda case: len(_visits_due(case, cf_schedule))
    done = lambda case: _visits_done(case, cf_schedule, "cf")
    return _done_due_count(cases, done, due)

def hd_day(cases):
    valid_cases = filter(lambda case: _delivered_at_in_timeframe(case, 'public', 240), cases)
    done = len(valid_cases)
    due = len(filter(lambda case:_visited_in_timeframe_of_birth(case, 1) , valid_cases))
    return _done_due(done, due)

def _get_time_of_birth(form):
    try:
        time_of_birth = form.xpath('form/data/child_info/case/update/time_of_birth')
        assert time_of_birth is not None
    except AssertionError:
        time_of_birth = safe_index(
            form.xpath('form/data/child_info')[0],
            'case/update/time_of_birth'.split('/')
        )
    return time_of_birth

def complications(cases, days):
    """
    DENOM: [
        any DELIVERY forms with (
            /data/complications = 'yes'
        ) in last 30 days
        PLUS any PNC forms with ( # 'any applicable from PNC forms with' (?)
            /data/abdominal_pain ='yes' or
            /data/bleeding = 'yes' or
            /data/discharge = 'yes' or
            /data/fever = 'yes' or
            /data/pain_urination = 'yes'
        ) in the last 30 days
        PLUS any REGISTRATION forms with (
            /data/abd_pain ='yes' or    # == abdominal_pain
            /data/fever = 'yes' or
            /data/pain_urine = 'yes' or    # == pain_urination
            /data/vaginal_discharge = 'yes'    # == discharge
        ) with /data/add in last 30 days
        PLUS any EBF forms with (
            /data/abdominal_pain ='yes' or
            /data/bleeding = 'yes' or
            /data/discharge = 'yes' or
            /data/fever = 'yes' or
            /data/pain_urination = 'yes'
        ) in last 30 days    # note, don't exist in EBF yet, but will shortly
    ]
    NUM: [
        filter (
            DELIVERY ? form.meta.timeStart - /data/child_info/case/update/time_of_birth,
            REGISTRATION|PNC|EBF ? form.meta.timeStart - case.add
        ) < `days` days
    ]
    """
    #https://bitbucket.org/dimagi/cc-apps/src/caab8f93c1e48d702b5d9032ef16c9cec48868f0/bihar/mockup/bihar_pnc.xml
    #https://bitbucket.org/dimagi/cc-apps/src/caab8f93c1e48d702b5d9032ef16c9cec48868f0/bihar/mockup/bihar_del.xml
    #https://bitbucket.org/dimagi/cc-apps/src/caab8f93c1e48d702b5d9032ef16c9cec48868f0/bihar/mockup/bihar_registration.xml
    #https://bitbucket.org/dimagi/cc-apps/src/caab8f93c1e48d702b5d9032ef16c9cec48868f0/bihar/mockup/bihar_ebf.xml
    PNC = 'http://bihar.commcarehq.org/pregnancy/pnc'
    DELIVERY = 'http://bihar.commcarehq.org/pregnancy/del'
    REGISTRATION = 'http://bihar.commcarehq.org/pregnancy/registration'
    EBF = 'https://bitbucket.org/dimagi/cc-apps/src/caab8f93c1e48d702b5d9032ef16c9cec48868f0/bihar/mockup/bihar_ebf.xml'
    _pnc_ebc_complications = [
        '/data/abdominal_pain',
        '/data/bleeding',
        '/data/discharge',
        '/data/fever',
        '/data/pain_urination',
    ]
    complications_by_form = {
        DELIVERY: [
            '/data/complications'
        ],
        PNC: _pnc_ebc_complications,
        EBF: _pnc_ebc_complications,
        REGISTRATION: [
            '/data/abd_pain',
            '/data/fever',
            '/data/pain_urine',
            '/data/vaginal_discharge',
        ],
    }
    now = datetime.utcnow()
    def get_forms(case, days=30):
        for action in case.actions:
            if action.date >= now - timedelta(days=days):
                yield action.xform

    done = 0
    due = 0
    days = timedelta(days=days)
    for case in cases:
        for form in get_forms(case):
            try:
                complication_paths = complications_by_form[form.xmlns]
            except KeyError:
                continue
            for p in complication_paths:
                if form.xpath('form' + p) == 'yes':
                    due += 1
                    if form.xmlns == DELIVERY:
                        add = _get_time_of_birth(form)
                    else:
                        add = get_add(case)
                    add = string_to_datetime(add)
                    if form.metatdata.timeStart - add < days:
                        done += 1
    return "%s/%s" % (done, due)