from collections import defaultdict
from couchdbkit import ResourceNotFound
from bihar.reports.indicators.filters import A_MONTH, is_pregnant_mother, is_newborn_child, get_add, get_edd,\
    mother_pre_delivery_columns, mother_post_delivery_columns
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.parsing import string_to_datetime
import datetime as dt
from bihar.reports.indicators.visits import visit_is, get_related_prop
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _

EMPTY = (0,0)

class CalculatorBase(object):
    """
    The public API for calculators. Which are used in both the indicator
    list and the client list.
    """
    def get_columns(self):
        raise NotImplementedError("Override this!")

    @memoized
    def as_row(self, case):
        raise NotImplementedError("Override this!")

    def filter(self, case):
        raise NotImplementedError("Override this!")

    @property
    def sortkey(self):
        # not having a sortkey shouldn't raise an exception so just
        # default to something reasonable
        return lambda case: case.name

class FilterOnlyCalculator(CalculatorBase):
    """
    A class for indicators that are used only by the client list.
    """
    show_in_indicators = False
    show_in_client_list = True

class IndicatorCalculator(CalculatorBase):
    """
    A class that, given a case, can tell you that cases contributions to the
    numerator and denominator of a particular indicator.
    """
    show_in_indicators = True
    show_in_client_list = False

    def numerator(self, case):
        raise NotImplementedError("Override this!")

    def denominator(self, case):
        raise NotImplementedError("Override this!")

    def filter(self, case):
        return bool(self.denominator(case))

    def _render(self, num, denom):
        return "%s/%s" % (num, denom)

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
        return self._render(num, denom)

class MemoizingFilterCalculator(FilterOnlyCalculator):
    # to avoid decorators everywhere. there might be a smarter way to do this
    @memoized
    def filter(self, case):
        return self._filter(case)

class MemoizingCalculatorMixIn(object):
    # same concept as MemoizingFilterCalculator

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

    @property
    def sortkey(self):
        return lambda case: self._numerator(case)

class MotherPreDeliveryMixIn(object):
    """
    Meant to be used with IndicatorCalculators shared defaults for stuff that
    shows up in the client list.
    """
    def get_columns(self):
        return (_("Name"), _("Husband's Name"), _("EDD"))

    def as_row(self, case):
        return mother_pre_delivery_columns(case)

    @property
    def sortkey(self):
        return lambda case: get_edd(case) or dt.datetime.max.date()

class MotherPreDeliverySummaryMixIn(MotherPreDeliveryMixIn):
    """
    Meant to be used with MotherPreDeliveryMixIn and SummaryValueMixIn, to
    provide extra shared defaults for clicking through the indicators.
    """
    def get_columns(self):
        cols = list(super(MotherPreDeliverySummaryMixIn, self).get_columns())
        return cols[:-1] + [_(self.summary_header)] + [cols[-1]]

    def as_row(self, case):
        cols = list(super(MotherPreDeliverySummaryMixIn, self).as_row(case))
        return cols[:-1] + [self.summary_value(case)] + [cols[-1]]

class MotherPostDeliveryMixIn(object):
    def get_columns(self):
        return (_("Name"), _("Husband's Name"), _("ADD"))

    def as_row(self, case):
        return mother_post_delivery_columns(case)

    @property
    def sortkey(self):
        # hacky way to sort by reverse add
        return lambda case: dt.datetime.today().date() - (get_add(case) or dt.datetime.max.date())

class MotherPostDeliverySummaryMixIn(MotherPostDeliveryMixIn):
    def get_columns(self):
        return super(MotherPostDeliverySummaryMixIn, self).get_columns() + (_(self.summary_header),)

    def as_row(self, case):
        return super(MotherPostDeliverySummaryMixIn, self).as_row(case) + (self.summary_value(case),)

def _num_denom(num, denom):
    return "%s/%s" % (num, denom)

def _in_timeframe(date, days):
    today = dt.datetime.today().date()
    return today - dt.timedelta(days=days) < date < today

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

def _delivered_in_timeframe(case, days):
    return is_pregnant_mother(case) and get_add(case) and _in_timeframe(case.add, days)

def _delivered_at_in_timeframe(case, at, days):
    at = at if isinstance(at, list) else [at]
    return getattr(case, 'birth_place', None) in at and _delivered_in_timeframe(case, days)

def _get_tob(case): # only guaranteed to be accurate within 24 hours
    tob = get_related_prop(case, "time_of_birth") or get_add(case) # use add if time_of_birth can't be found
    if isinstance(tob, dt.date):
        tob = dt.datetime.combine(tob, dt.datetime.time(dt.datetime.now())) #convert date to dt.datetime
    return tob

def _get_time_of_visit_after_birth(case):
    form = _get_form(case, action_filter=lambda a: a.updated_unknown_properties.get("add", None))
    return form.xpath('form/meta/timeStart')

def _visited_in_timeframe_of_birth(case, days):
    visit_time = _get_time_of_visit_after_birth(case)
    time_birth = _get_tob(case)
    if visit_time and time_birth:
        return time_birth < visit_time < time_birth + dt.timedelta(days=days)
    return False

def _get_actions(case, action_filter=lambda a: True):
    for action in case.actions:
        if action_filter(action):
            yield action

def _get_forms(case, action_filter=lambda a: True, form_filter=lambda f: True):
    for action in _get_actions(case, action_filter=action_filter):
        if getattr(action, 'xform', None) and form_filter(action.xform):
            yield action.xform

def _get_action(case, action_filter=lambda a: True):
    """
    returns the first action that passes through the action filter
    """
    ga = _get_actions(case, action_filter=action_filter)
    try:
        return ga.next()
    except StopIteration:
        return None

def _get_form(case, action_filter=lambda a: True, form_filter=lambda f: True):
    """
    returns the first form that passes through both filter functions
    """
    gf = _get_forms(case, action_filter=action_filter, form_filter=form_filter)
    try:
        return gf.next()
    except StopIteration:
        return None

def _get_prop_from_forms(case, property):
    form = _get_form(case, form_filter=lambda f: f.form.get(property, None))
    return form.form[property] if form else None

def _get_xpath_from_forms(case, path):
    form = _get_form(case, form_filter=lambda f: f.xpath("form/%s" % path))
    return form.xpath("form/%s" % path) if form else None

def _newborn(case, days=None): # :(
    def af(action):
        if not days:
            return True
        now = dt.datetime.now()
        return now - dt.timedelta(days=days) <= action.date <= now

    def recently_delivered(case):
        return _get_form(case, action_filter=af, form_filter=lambda f: f.form.get('recently_delivered', "") == 'yes')

    return is_pregnant_mother(case) and\
           (recently_delivered(case) or get_related_prop(case, 'birth_status') == "live_birth")

def _recent_newborn(case, days=None):
    def af(action):
        if not days:
            return True
        now = dt.datetime.now()
        return now - dt.timedelta(days=days) <= action.date <= now

    def new_delivery(form):
        return form.form.get('recently_delivered', "") == 'yes' or form.form.get('has_delivered', "") == 'yes'

    return _get_form(case, action_filter=af, form_filter=new_delivery)

def _adopted_fp(case):
    def ff(f):
        return f.form.get('post_partum_fp', "") == 'yes'
    return _get_form(case, form_filter=ff) and getattr(case, 'family_planning_type', "") != 'no_fp_at_delivery'

def _expecting_soon(case):
    return is_pregnant_mother(case) and get_edd(case) and _in_timeframe(case.edd, -30)



# NOTE: cases in, values out might not be the right API
# but it's what we need for the first set of stuff.
# might want to revisit.

# NOTE: this is going to be slooooow


class HDDayCalculator(SummaryValueMixIn, MotherPreDeliverySummaryMixIn,
                      MemoizingCalculatorMixIn, IndicatorCalculator):

    def _numerator(self, case):
        return 1 if _visited_in_timeframe_of_birth(case, 1) else 0

    def _denominator(self, case):
        return 1 if _delivered_at_in_timeframe(case, 'home', 30) else 0

class IDDayCalculator(HDDayCalculator):

    def _denominator(self, case):
        return 1 if _delivered_at_in_timeframe(case, ['private', 'public'], 30) else 0


class IDNBCalculator(IDDayCalculator):

    def _denominator(self, case):
        if super(IDNBCalculator, self)._denominator(case) and get_related_prop(case, 'birth_status') == "live_birth":
            return 1
        else:
            return 0

    def _numerator(self, case):
        dtf = _get_prop_from_forms(case, 'date_time_feed')
        tob = get_related_prop(case, 'time_of_birth')
        if dtf and tob:
            return 1 if dtf - tob <= dt.timedelta(hours=1) else 0
        return 0


class PTLBCalculator(SummaryValueMixIn, MotherPreDeliverySummaryMixIn,
                     MemoizingCalculatorMixIn, IndicatorCalculator):

    def _preterm(self, case):
        return True if getattr(case, 'term', None) == "pre_term" else False

    def _numerator(self, case):
        return 1 if self._preterm(case) else 0

    def _denominator(self, case):
        return 1 if _newborn(case, 30) else 0

class LT2KGLBCalculator(PTLBCalculator): # should change name probs

    def _lt2(self, case):
        w = _get_xpath_from_forms(case, "child_info/weight")
        fw = _get_xpath_from_forms(case, "child_info/first_weight")
        return True if (w is not None and w < 2.0) or (fw is not None and fw < 2.0) else False

    def _numerator(self, case):
        return 1 if self._lt2(case) else 0

class VWOCalculator(LT2KGLBCalculator):

    def _weak_baby(self, case):
        return True if _newborn(case, 30) and (self._preterm(case) or self._lt2(case)) else False

    def _denominator(self, case):
        return 1 if self._weak_baby(case) else 0

    def _numerator(self, case):
        return 1 if _visited_in_timeframe_of_birth(case, 1) else 0

class SimpleListMixin(object):
    def _render(self, num, denom):
        return str(denom)

    def _numerator(self, case):
        return 0

class S2SCalculator(FilterOnlyCalculator, VWOCalculator):

    def _denominator(self, case):
        return 1 if self._weak_baby(case) and _get_xpath_from_forms(case, "child_info/skin_to_skin") == 'no' else 0

class FVCalculator(S2SCalculator):

    def _denominator(self, case):
        return 1 if self._weak_baby(case) and _get_xpath_from_forms(case, "child_info/feed_vigour") == 'no' else 0

class MMCalculator(FilterOnlyCalculator, SummaryValueMixIn, MotherPreDeliverySummaryMixIn,
                   MemoizingCalculatorMixIn, IndicatorCalculator):

    def _action_within_timeframe(self, action, days):
        now = dt.datetime.now()
        return now - dt.timedelta(days=days) <= action.date <= now

    def _denominator(self, case):
        def afn(a):
            return self._action_within_timeframe(a, 30) and a.updated_known_properties.get('mother_alive', None) == "no"

        if is_pregnant_mother(case):
            action = _get_action(case, action_filter=afn)
            return 1 if action else 0
        return 0

class IMCalculator(MMCalculator):

    def _denominator(self, case):
        def afn(a):
            return self._action_within_timeframe(a, 30) and a.updated_known_properties.get('child_alive', None) == "no"

        if is_newborn_child(case):
            action = _get_action(case, action_filter=afn)
            return 1 if action else 0
        return 0

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

class ComplicationsCalculator(SummaryValueMixIn, MotherPostDeliverySummaryMixIn,
    MemoizingCalculatorMixIn, IndicatorCalculator):
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
    show_in_client_list = True
    show_in_indicators = True

    def __init__(self, days, now=None):
        super(ComplicationsCalculator, self).__init__()
        self.now = now or dt.datetime.utcnow()
        self.days = dt.timedelta(days=days)

    def _numerator(self, case):
        return self._calculate_both(case)[0]

    def _denominator(self, case):
        return self._calculate_both(case)[1]

    @property
    def summary_header(self):
        if self.days.days > 1:
            return _("Identified in %s days") % self.days.days
        else:
            return _("Identified in %s hours") % (self.days.days*24)

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
                add = string_to_datetime(add).date()
                if form.metadata.timeStart.date() - add <= self.days:
                    has_recent_complication = True
                    break

        return has_recent_complication, has_complication

class FPCalculator(SummaryValueMixIn, MotherPreDeliverySummaryMixIn,
                    MemoizingCalculatorMixIn, IndicatorCalculator):

    def _numerator(self, case):
        return 1 if getattr(case, 'couple_interested', None) == 'Yes' else 0

    def _denominator(self, case):
        return 1 if _recent_newborn(case, 300000) else 0

class AFPCalculator(FPCalculator):

    def _numerator(self, case):
        return 1 if _adopted_fp(case) else 0

    def _denominator(self, case):
        fp_class = super(AFPCalculator, self)
        return 1 if fp_class._denominator(case) and fp_class.numerator(case) else 0

class EFPCalculator(FPCalculator):

    def _denominator(self, case):
        return 1 if is_pregnant_mother(case) else 0

class NOFPCalculator(FilterOnlyCalculator, FPCalculator):

    def _denominator(self, case):
        return 1 if _recent_newborn(case, 7) and getattr(case, 'family_planning_type', "") != 'no_fp_at_delivery' else 0

class PFPCalculator(NOFPCalculator):

    def _denominator(self, case):
        return 1 if _expecting_soon(case) and getattr(case, 'couple_interested', "") == "yes" else 0


