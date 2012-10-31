from bihar.reports.indicators.filters import A_MONTH, is_pregnant_mother,\
    in_second_trimester, in_third_trimester
from datetime import datetime


EMPTY = (0,0)

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

# NOTE: cases in, values out might not be the right API
# but it's what we need for the first set of stuff.
# might want to revisit.

# NOTE: there is currently a lot of copy/paste here, but 
# until the indicators are fully defined that's fine.
def bp2_last_month(cases):
    # NOTE: this is going to be slooooow
    done = due = 0
    for case in cases:
        if is_pregnant_mother(case):
            edd = getattr(case, 'edd', None)
            if edd:
                for a in case.actions:
                    # relevant
                    if a.date > datetime.today() - A_MONTH \
                        and in_second_trimester(edd, a.date.date()) \
                        and _has_bp_visit(a) \
                        and _visit_is(a, 'bp'):
                        done += 1
                        due += 1 # NOTE: this isn't right but i'm not sure how it should be done.
                        break
    
    return _done_due(done, due)

def bp3_last_month(cases):
    done = due = 0
    for case in cases:
        if is_pregnant_mother(case):
            edd = getattr(case, 'edd', None)
            if edd:
                for a in case.actions:
                    # relevant
                    if a.date > datetime.today() - A_MONTH \
                        and in_third_trimester(edd, a.date.date()) \
                        and _has_bp_visit(a) \
                        and _visit_is(a, 'bp'):
                        done += 1
                        due += 1 # NOTE: this isn't right but i'm not sure how it should be done.
                        break
    
    return _done_due(done, due)

def pnc_last_month(cases):
    done = due = 0
    for case in cases:
        if is_pregnant_mother(case):
            for a in case.actions:
                if a.date > datetime.today() - A_MONTH \
                    and _has_pnc_visit(a) \
                    and _visit_is(a, 'pnc'):
                    done += 1
                    due += 1 # NOTE: this isn't right but i'm not sure how it should be done.

    return _done_due(done, due)

def eb_last_month(cases):
    done = due = 0
    for case in cases:
        if is_pregnant_mother(case):
            for a in case.actions:
                if a.date > datetime.today() - A_MONTH \
                    and _has_eb_visit(a) \
                    and _visit_is(a, 'eb'):
                    done += 1
                    due += 1 # NOTE: this isn't right but i'm not sure how it should be done.

    return _done_due(done, due)

def cf_last_month(cases):
    done = due = 0
    for case in cases:
        if is_pregnant_mother(case):
            for a in case.actions:
                if a.date > datetime.today() - A_MONTH \
                    and _has_cf_visit(a) \
                    and _visit_is(a, 'cf'):
                    done += 1
                    due += 1 # NOTE: this isn't right but i'm not sure how it should be done.

    return _done_due(done, due)
