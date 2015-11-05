from custom.bihar.calculations.pregnancy import VisitedQuickly
from custom.bihar.calculations.types import DoneDueCalculator, TotalCalculator, CaseCalculator
from custom.bihar.calculations.utils.calculations import get_related_prop
from custom.bihar.calculations.utils.filters import is_pregnant_mother, get_add, A_MONTH
from custom.bihar.calculations.utils.xmlns import REGISTRATION
from custom.bihar.calculations.utils.calculations import get_form
from django.utils.translation import ugettext_noop as _
import fluff


def _get_xpath_from_forms(case, path):
    form = get_form(case, form_filter=lambda f: f.get_data("form/%s" % path))
    return form.get_data("form/%s" % path) if form else None


def is_preterm(case):
    return getattr(case, 'term', None) == "pre_term"


def less_than_two_kilos(case):
    w = _get_xpath_from_forms(case, "child_info/weight")
    fw = _get_xpath_from_forms(case, "child_info/first_weight")
    return (w is not None and w < 2.0) or (fw is not None and fw < 2.0)


def is_weak_baby(case):
    return is_preterm(case) or less_than_two_kilos(case)


def is_recently_delivered(case):
    return get_form(
        case,
        action_filter=lambda a: a.xform_xmlns == REGISTRATION,
        form_filter=lambda f: f.form.get('recently_delivered', "") == 'yes'
    )


def is_newborn(case):
    return is_pregnant_mother(case) and (
        is_recently_delivered(case)
        or get_related_prop(case, 'birth_status') == "live_birth"
    ) and get_add(case)


class Newborn(CaseCalculator):
    window = A_MONTH
    include_closed = True

    @fluff.filter_by
    def is_newborn(self, case):
        return is_newborn(case)


class NewbornDoneDue(Newborn, DoneDueCalculator):
    @fluff.date_emitter
    def total(self, case):
        yield get_add(case)


class PretermNewborn(NewbornDoneDue):
    _("Preterm births")

    @fluff.date_emitter
    def numerator(self, case):
        if is_preterm(case):
            yield get_add(case)


class LessThan2Kilos(NewbornDoneDue):
    _("infants < 2kg")

    @fluff.date_emitter
    def numerator(self, case):
        if less_than_two_kilos(case):
            yield get_add(case)


class WeakNewborn(Newborn):
    @fluff.filter_by
    def weak_baby(self, case):
        return is_weak_baby(case)


class VisitedWeakNewborn(VisitedQuickly, WeakNewborn):
    _("visited Weak Newborn within 24 hours of birth by FLW")
    pass


class NoSkinToSkin(TotalCalculator, WeakNewborn):
    _("weak newborn not receiving skin to skin care message by FLW")

    @fluff.filter_by
    def no_skin_to_skin(self, case):
        return _get_xpath_from_forms(case, "child_info/skin_to_skin") == 'no'

    @fluff.date_emitter
    def total(self, case):
        yield get_add(case)


class NotBreastfeedingVigorously(TotalCalculator, WeakNewborn):
    _("weak newborn not breastfeeding vigorously ")

    @fluff.filter_by
    def not_breastfeeding_vigorously(self, case):
        return _get_xpath_from_forms(case, "child_info/feed_vigour") == 'no'

    @fluff.date_emitter
    def total(self, case):
        yield get_add(case)
