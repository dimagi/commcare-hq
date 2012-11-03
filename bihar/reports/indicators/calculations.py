from bihar.reports.indicators.filters import A_MONTH, is_pregnant_mother,\
    in_second_trimester, in_third_trimester
from datetime import datetime, timedelta


EMPTY = (0,0)
GRACE_PERIOD = timedelta(days=7)


def _done_due(done, due):
    return "%s/%s" % (done, due)

def _any_action_property(action, props):
    for p in props:
        if p in action.updated_unknown_properties and action.updated_unknown_properties[p]:
            return True
    return False
    
def _visit_is(action, visit_type):
    return action.updated_unknown_properties.get('last_visit_type', None) == visit_type

def _has_bp_visit(action):
    return _any_action_property(action, ('date_bp_%s' % i for i in range(1, 4)))

def _has_pnc_visit(action):
    return _any_action_property(action, ('date_pnc_%s' % i for i in range(1, 4)))

def _has_eb_visit(action):
    return _any_action_property(action, ('date_eb_%s' % i for i in range(1, 7)))

def _has_cf_visit(action):
    return _any_action_property(action, ('date_eb_%s' % i for i in range(1, 8)))

def _in_last_month(date):
    today = datetime.today().date()
    return date < today - A_MONTH < today

def _mother_due_in_window(case, days):
    get_edd = lambda case: getattr(case, 'edd', None)
    get_duedate = lambda case: case.edd - timedelta(days=days) + GRACE_PERIOD
    return is_pregnant_mother(case) and get_edd(case) and _in_last_month(get_duedate(case))
        
def _mother_delivered_in_window(case, days):
    get_add = lambda case: getattr(case, 'add', None)
    get_duedate = lambda case: case.add + timedelta(days=days) + GRACE_PERIOD
    return is_pregnant_mother(case) and get_add(case) and _in_last_month(get_duedate(case))
        
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
    return [i +1 for i, days in enumerate(schedule) \
            if _mother_delivered_in_window(case, days)]

def _visits_done(case, schedule, type):
    due = _visits_due(case, schedule)
    count = len(filter(lambda a: _visit_is(a, type), case.actions))
    return len(v for v in due if count > v)
    
# NOTE: cases in, values out might not be the right API
# but it's what we need for the first set of stuff.
# might want to revisit.

# NOTE: this is going to be slooooow
def bp2_last_month(cases):
    due = lambda case: 1 if _mother_due_in_window(case, 75) else 0
    # make sure they've done 2 bp visits
    done = lambda case: 1 if len(filter(lambda a: _visit_is(a, 'bp'), case.actions)) >= 2 else 0
    return _done_due_count(cases, due, done)    
    
def bp3_last_month(cases):
    due = lambda case: 1 if _mother_due_in_window(case, 45) else 0
    # make sure they've done 2 bp visits
    done = lambda case: 1 if len(filter(lambda a: _visit_is(a, 'bp'), case.actions)) >= 3 else 0
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
