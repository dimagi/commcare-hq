import datetime
from django.utils.translation import ugettext_noop as _
from custom.bihar.calculations.newborn import is_recently_delivered
from custom.bihar.calculations.types import DoneDueCalculator, TotalCalculator, AddCalculator
from custom.bihar.calculations.utils.filters import get_add, A_MONTH, is_pregnant_mother, get_edd
from custom.bihar.calculations.utils.xmlns import DELIVERY
from custom.bihar.calculations.utils.calculations import get_form
import fluff


def adopted_fp(case):
    def ff(f):
        return f.form.get('post_partum_fp', "") == 'yes'
    return get_form(case, form_filter=ff) and getattr(case, 'family_planning_type', "") != 'no_fp_at_delivery'


def couple_interested_in_fp(case):
    return getattr(case, 'couple_interested', '') == 'yes'


def has_delivered(case):
    return get_form(
        case,
        action_filter=lambda a: a.xform_xmlns == DELIVERY,
        form_filter=lambda f: f.form.get('has_delivered', '') == 'yes'
    )


def has_delivered_at_all(case):
    return has_delivered(case) or is_recently_delivered(case)


class FamilyPlanning(DoneDueCalculator, AddCalculator):
    _("# Expressed interest in family planning / # deliveries in last 30 days")

    window = A_MONTH

    def filter(self, case):
        return has_delivered_at_all(case)

    @fluff.date_emitter
    def numerator(self, case):
        if couple_interested_in_fp(case):
            yield get_add(case)


class AdoptedFP(DoneDueCalculator, AddCalculator):
    _("# Adopted FP / "
      "# expressed interest in family planning & delivered in last 30 days")

    window = A_MONTH

    def filter(self, case):
        return has_delivered_at_all(case) and couple_interested_in_fp(case)

    @fluff.date_emitter
    def numerator(self, case):
        if adopted_fp(case):
            yield get_add(case)


class InterestInFP(DoneDueCalculator):
    _("# expressed interest in family planning / total # clients")

    window = None

    def filter(self, case):
        return is_pregnant_mother(case)

    @fluff.null_emitter
    def numerator(self, case):
        if couple_interested_in_fp(case):
            yield None

    @fluff.null_emitter
    def total(self, case):
        yield None


class NoFP(TotalCalculator):
    _("clients who delivered in last 7 days and have not yet adopted FP")

    window = datetime.timedelta(days=7)

    def filter(self, case):
        return (
            has_delivered_at_all(case)
            and getattr(case, 'family_planning_type', '') in (
                'no_fp_at_delivery',
                'no_fp_adopted_at_delivery',
            )
            and get_add(case)
        )

    @fluff.date_emitter
    def total(self, case):
        yield get_add(case)


class PregnantInterestInFP(TotalCalculator):
    _("# clients who whose EDD is in 30 days and have expressed interest in FP")

    window = -A_MONTH

    def filter(self, case):
        return is_pregnant_mother(case) and get_edd(case) and couple_interested_in_fp(case)

    @fluff.date_emitter
    def total(self, case):
        yield get_edd(case)
