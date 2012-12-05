from collections import defaultdict
from couchdbkit import ResourceNotFound
from bihar.reports.indicators.filters import A_MONTH, is_pregnant_mother, get_add, get_edd,\
    mother_pre_delivery_columns
from couchforms.safe_index import safe_index
from dimagi.utils.parsing import string_to_datetime
import datetime as dt
from bihar.reports.indicators.visits import visit_is, get_related_prop
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _

EMPTY = (0,0)
GRACE_PERIOD = dt.timedelta(days=7)

class IndicatorCalculator(object):
    """
    A class that, given a case, can tell you that cases contributions to the
    numerator and denominator of a particular indicator.
    """

    def __init__(self, *args, **kwargs):
        pass

    def numerator(self, case):
        raise NotImplementedError("Override this!")

    def denominator(self, case):
        raise NotImplementedError("Override this!")

    def get_columns(self):
        raise NotImplementedError("Override this!")

    @memoized
    def as_row(self, case):
        raise NotImplementedError("Override this!")

    def filter(self, case):
        return bool(self.denominator(case))

    @memoized
    def display(self, cases):
        num = denom = 0
        for case in cases:
            denom_diff = self.denominator(case)
            if denom_diff:
                denom += denom_diff
                num_diff = self.numerator(case)
                assert num_diff <= denom_diff
                # this is to prevent the numerator from ever passing the denominator
                # though is probably not totally accurate
                num += num_diff
        return "%s/%s" % (num, denom)

class MemoizingCalculatorMixIn(object):
    # to avoid decorators everywhere. there might be a smarter way to do this

    @memoized
    def numerator(self, case):
        return self._numerator(case)

    @memoized
    def denominator(self, case):
        return self._denominator(case)

class SummaryValueMixIn(object):
    """
    Meant to be used in conjunction with IndicatorCalculators, allows you to
    define text that should show up in the client list if the numerator is
    set, if the denominator is set, or neither is set.
    
    Also provides sensible defaults.
    """
    numerator_text = ugettext_noop("Yes")
    denominator_text = ugettext_noop("No")
    neither_text = ugettext_noop("N/A")
    summary_header = "Value?"

    def summary_value(self, case):
        if self.denominator(case):
            return _(self.numerator_text) if self.numerator(case) \
                else _(self.denominator_text)
        return _(self.neither_text)

class DoneDueMixIn(SummaryValueMixIn):
    summary_header = ugettext_noop("Visit Status")
    numerator_text = ugettext_noop("Done")
    denominator_text = ugettext_noop("Due")

class MotherPreDeliveryMixIn(object):
    """
    Meant to be used with IndicatorCalculators and SummaryValueMixIn, to
    provide shared defaults for stuff that shows up in the client list.
    """
    def get_columns(self):
        return [_("Name"), _("Husband's Name"), _("EDD"), _(self.summary_header)]
    
    def as_row(self, case):
        return mother_pre_delivery_columns(case) + (self.summary_value(case), )
    
class BP2Calculator(MotherPreDeliveryMixIn, MemoizingCalculatorMixIn, DoneDueMixIn, IndicatorCalculator):

    def _numerator(self, case):
        return 1 if _mother_due_in_window(case, 75) else 0

    def _denominator(self, case):
        return 1 if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= 2 else 0

def _num_denom(num, denom):
    return "%s/%s" % (num, denom)

def _in_last_month(date):
    today = dt.datetime.today().date()
    return today - A_MONTH < date < today

def _in_timeframe(date, days):
    today = dt.datetime.today().date()
    return today - dt.timedelta(days=days) < date < today

def _mother_due_in_window(case, days):
    get_visitduedate = lambda case: case.edd - dt.timedelta(days=days) + GRACE_PERIOD
    return is_pregnant_mother(case) and get_edd(case) and _in_last_month(get_visitduedate(case))
        
def _mother_delivered_in_window(case, days):
    get_visitduedate = lambda case: case.add + dt.timedelta(days=days) + GRACE_PERIOD
    return is_pregnant_mother(case) and get_add(case) and _in_last_month(get_visitduedate(case))

def _num_denom_count(cases, num_func, denom_func):
    num = denom = 0
    for case in cases:
        denom_diff = denom_func(case)
        if denom_diff:
            denom += denom_diff
            num_diff = num_func(case)
            assert num_diff <= denom_diff
            # this is to prevent the numerator from ever passing the denominator
            # though is probably not totally accurate
            num += num_diff
    return _num_denom(num, denom)

def _visits_due(case, schedule):
    return [i + 1 for i, days in enumerate(schedule) \
            if _mother_delivered_in_window(case, days)]

def _visits_done(case, schedule, type):
    due = _visits_due(case, schedule)
    count = len(filter(lambda a: visit_is(a, type), case.actions))
    return len([v for v in due if count > v])

def _delivered_in_timeframe(case, days):
    return is_pregnant_mother(case) and get_add(case) and _in_timeframe(case.add, days)

def _delivered_at_in_timeframe(case, at, days):
    at = at if isinstance(at, list) else [at]
    return getattr(case, 'birth_place', None) in at and _delivered_in_timeframe(case, days)

def _get_time_of_visit_after_birth(case):
    for action in case.actions:
        if action.updated_unknown_properties.get("add", None):
            return action.date
    return None

def _visited_in_timeframe_of_birth(case, days):
    visit_time = _get_time_of_visit_after_birth(case)
    time_birth = get_related_prop(case, "time_of_birth") or get_add(case) # use add if time_of_birth can't be found
    if visit_time and time_birth:
        if isinstance(time_birth, dt.date):
            time_birth = dt.datetime.combine(time_birth, dt.datetime.time(dt.datetime.now())) #convert date to dt.datetime
        return time_birth < visit_time < time_birth + dt.timedelta(days=days)
    return False

def _get_actions(case, action_filter=lambda a: True):
    for action in case.actions:
        if action_filter(action):
            yield action

def _get_forms(case, action_filter=lambda a: True, form_filter=lambda f: True):
    for action in _get_actions(case, action_filter):
        if getattr(action, 'xform', None) and form_filter(action.xform):
            yield action.xform

def _weak_babies(case, days=None): # :(
    def af(action):
        if not days:
            return True
        now = dt.datetime.now()
        return now - dt.timedelta(days=days) <= action.date <= now

    def recently_delivered(case):
        for form in _get_forms(case, action_filter=af):
            if form.xpath("form/data/recently_delivered") == 'yes':
                return True
        return False

    return is_pregnant_mother(case) and\
           (recently_delivered(case) or get_related_prop(case, 'birth_status') == "live_birth")


    
# NOTE: cases in, values out might not be the right API
# but it's what we need for the first set of stuff.
# might want to revisit.

# NOTE: this is going to be slooooow
def bp3_last_month(cases):
    due = lambda case: 1 if _mother_due_in_window(case, 45) else 0
    # make sure they've done 2 bp visits
    done = lambda case: 1 if len(filter(lambda a: visit_is(a, 'bp'), case.actions)) >= 3 else 0
    return _num_denom_count(cases, due, done)    
    
def pnc_last_month(cases):
    pnc_schedule = (1, 3, 6)
    due = lambda case: len(_visits_due(case, pnc_schedule))
    done = lambda case: _visits_done(case, pnc_schedule, "pnc")
    return _num_denom_count(cases, done, due)

def eb_last_month(cases):
    eb_schedule = (14, 28, 60, 90, 120, 150)
    due = lambda case: len(_visits_due(case, eb_schedule))
    done = lambda case: _visits_done(case, eb_schedule, "eb")
    return _num_denom_count(cases, done, due)

def cf_last_month(cases):
    cf_schedule_in_months = (6, 7, 8, 9, 12, 15, 18)
    cf_schedule = (m * 30 for m in cf_schedule_in_months)
    due = lambda case: len(_visits_due(case, cf_schedule))
    done = lambda case: _visits_done(case, cf_schedule, "cf")
    return _num_denom_count(cases, done, due)

class HDDayCalculator(SummaryValueMixIn, MotherPreDeliveryMixIn, MemoizingCalculatorMixIn, IndicatorCalculator):

    def _numerator(self, case):
        return 1 if _visited_in_timeframe_of_birth(case, 1) else 0

    def _denominator(self, case):
        return 1 if _delivered_at_in_timeframe(case, 'home', 30) else 0

class IDDayCalculator(HDDayCalculator):

    def _denominator(self, case):
        return 1 if _delivered_at_in_timeframe(case, ['private', 'public'], 3000) else 0

class IDNBCalculator(IDDayCalculator):

    def _denominator(self, case):
        if super(IDNBCalculator, self)._denominator(case) and get_related_prop(case, 'birth_status') == "live_birth":
            return 1
        else:
            return 0

    def _numerator(self, case):
        dtf = get_related_prop(case, 'date_time_feed')
        tob = get_related_prop(case, 'time_of_birth')
        if dtf and tob:
            return 1 if dtf - tob <= dt.timedelta(hours=1) else 0
        return 0

class PTLBCalculator(SummaryValueMixIn, MotherPreDeliveryMixIn, MemoizingCalculatorMixIn, IndicatorCalculator):

    def _numerator(self, case):
        return 1 if getattr(case, 'term', None) == "pre_term" else 0

    def _denominator(self, case):
        return 1 if _weak_babies(case, 30) else 0

class LT2KGLBCalculator(PTLBCalculator): # should change name probs

    def _numerator(self, case):
        w = get_related_prop(case, 'weight')
        fw = get_related_prop(case, 'first_weight')
        return 1 if (w is not None and w < 2.0) or (fw is not None and fw < 2.0) else 0

def _get_time_of_birth(form):
    try:
        time_of_birth = form.xpath('form/child_info/case/update/time_of_birth')
        assert time_of_birth is not None
    except AssertionError:
        time_of_birth = safe_index(
            form.xpath('form/child_info')[0],
            'case/update/time_of_birth'.split('/')
        )
    return time_of_birth

class ComplicationsCalculator(MotherPreDeliveryMixIn, MemoizingCalculatorMixIn, DoneDueMixIn, IndicatorCalculator):
    """
        DENOM: [
            any DELIVERY forms with (
                complications = 'yes'
            ) in last 30 days
            PLUS any PNC forms with ( # 'any applicable from PNC forms with' (?)
                abdominal_pain ='yes' or
                bleeding = 'yes' or
                discharge = 'yes' or
                fever = 'yes' or
                pain_urination = 'yes'
            ) in the last 30 days
            PLUS any REGISTRATION forms with (
                abd_pain ='yes' or    # == abdominal_pain
                fever = 'yes' or
                pain_urine = 'yes' or    # == pain_urination
                vaginal_discharge = 'yes'    # == discharge
            ) with add in last 30 days
            PLUS any EBF forms with (
                abdominal_pain ='yes' or
                bleeding = 'yes' or
                discharge = 'yes' or
                fever = 'yes' or
                pain_urination = 'yes'
            ) in last 30 days    # note, don't exist in EBF yet, but will shortly
        ]
        NUM: [
            filter (
                DELIVERY ? form.meta.timeStart - child_info/case/update/time_of_birth,
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
        'abdominal_pain',
        'bleeding',
        'discharge',
        'fever',
        'pain_urination',
    ]
    complications_by_form = {
        DELIVERY: [
            'complications'
        ],
        PNC: _pnc_ebc_complications,
        EBF: _pnc_ebc_complications,
        REGISTRATION: [
            'abd_pain',
            'fever',
            'pain_urine',
            'vaginal_discharge',
        ],
    }

    def __init__(self, days, now=None):
        super(ComplicationsCalculator, self).__init__()
        self.now = now or dt.datetime.utcnow()
        self.days = dt.timedelta(days=days)

    def _numerator(self, case):
        return self._calculate_both(case)[0]

    def _denominator(self, case):
        return self._calculate_both(case)[1]

    @memoized
    def get_forms(self, case, days=30):
        xform_ids = set()
        for action in case.actions:
            if action.xform_id not in xform_ids:
                xform_ids.add(action.xform_id)
                if self.now - dt.timedelta(days=days) <= action.date <= self.now:
                    try:
                        yield action.xform
                    except ResourceNotFound:
                        pass

    def get_forms_with_complications(self, case):
        for form in self.get_forms(case):
            try:
                complication_paths = self.complications_by_form[form.xmlns]
            except KeyError:
                continue
            else:
                for p in complication_paths:
                    if form.xpath('form/' + p) == 'yes':
                        yield form

    @memoized
    def _calculate_both(self, case):
        has_complication = False
        has_recent_complication = False
        if case.type == 'cc_bihar_pregnancy':
            for form in self.get_forms_with_complications(case):
                has_complication = True
                if form.xmlns == self.DELIVERY:
                    add = _get_time_of_birth(form)
                else:
                    add = get_add(case)
                add = string_to_datetime(add)
                if form.metadata.timeStart - add < self.days:
                    has_recent_complication = True
                    break

        return has_recent_complication, has_complication

def complications(cases, days, now=None):
    return ComplicationsCalculator(days=days, now=now).display(cases)
