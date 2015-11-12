import datetime
import logging
from django.utils.translation import ugettext_noop as _
from custom.bihar.calculations.pregnancy import BirthPlace
from custom.bihar.calculations.types import TotalCalculator, AddCalculator
from custom.bihar.calculations.utils.calculations import get_actions, get_forms
from custom.bihar.calculations.utils.filters import is_pregnant_mother, A_MONTH, is_newborn_child
from custom.bihar.calculations.utils.xmlns import DELIVERY, PNC
import fluff


def latest_action_date(actions):
    dates = [action.date for action in actions]
    if dates:
        return max(dates)
    else:
        return None


def is_stillborn(case):
    properties = (
        'child_cried',
        'child_breathing',
        'child_movement',
        'child_heartbeats'
    )
    for xform in get_forms(case, action_filter=lambda a: a.xform_xmlns == DELIVERY):
        if xform.form.get('has_delivered') != 'yes':
            continue
        for p in properties:
            value = xform.get_data('form/child_info/%s' % p)
            if not value:
                child_infos = xform.get_data('form/child_info')
                if not child_infos:
                    continue
                for child_info in child_infos:
                    child_info.get(p)
                    # no idea whether this is a thing that can get called
                    logging.debug('(nested) %s: %s' % (p, value))
                    if value != 'no':
                        return False
            else:
                if value != 'no':
                    return False
        return True


class MMCalculator(TotalCalculator):
    """
    ([DELIVERY form] OR [PNC form]) filter by mother_alive = 'no'
    and where date_death - form_case_update_add <= 42

    """
    _('Maternal mortality')

    window = datetime.timedelta(days=42)

    def filter(self, case):
        return is_pregnant_mother(case)

    @fluff.date_emitter
    def total(self, case):

        def mother_died(a):
            return (
                a.updated_known_properties.get('mother_alive') == 'no'
                and a.xform_xmlns in (DELIVERY, PNC)
            )

        for xform in get_forms(case, action_filter=mother_died, reverse=True):
            yield xform.form.get('date_death')
            # yield at most one
            break


class IMCalculator(TotalCalculator):
    """
    (
        [DELIVERY form] child_alive = 'no' and  chld_date_death - form_case_update_add
        OR [PNC form] child_alive = 'no' and chld_date_death - form_case_update_add
    ) <= 365
    """
    _('Infant mortality')

    window = datetime.timedelta(days=365)

    def filter(self, case):
        return is_newborn_child(case)

    @fluff.date_emitter
    def total(self, case):
        def child_died(a):
            return a.updated_known_properties.get('child_alive', None) == "no"

        date = latest_action_date(get_actions(case, action_filter=child_died))
        if date:
            yield date


class StillBirth(TotalCalculator, AddCalculator):

    window = A_MONTH
    include_closed = True

    @fluff.filter_by
    def is_stillborn(self, case):
        return is_stillborn(case)


class StillBirthPlace(StillBirth, BirthPlace):
    _('Still Births at Government Hospital')
    _('Still Births at Home')

    window = A_MONTH


class LiveBirth(TotalCalculator, AddCalculator):
    _('Live Births')

    window = A_MONTH

    @fluff.filter_by
    def not_stillborn(self, case):
        return not is_stillborn(case)
