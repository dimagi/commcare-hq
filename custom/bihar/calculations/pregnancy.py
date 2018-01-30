from __future__ import absolute_import
import datetime
from custom.bihar.calculations.types import CaseCalculator, DoneDueCalculator, AddCalculator
from custom.bihar.calculations.utils.calculations import get_related_prop, get_form
from custom.bihar.calculations.utils.filters import get_add, A_MONTH, A_DAY
import fluff
import six


def _get_tob(case):  # only guaranteed to be accurate within 24 hours
    import couchdbkit
    tob = get_related_prop(case, "time_of_birth") or '00:00:00'

    tob = couchdbkit.schema.TimeProperty().to_python(tob)
    tob = datetime.datetime.combine(get_add(case), tob)  # convert date to dt.datetime
    return tob


def _get_time_of_visit_after_birth(case):
    form = get_form(case, action_filter=lambda a: a.updated_unknown_properties.get("add", None))
    return form.get_data('form/meta/timeStart') if form else None


def _get_prop_from_forms(case, property):
    form = get_form(case, form_filter=lambda f: f.form.get(property, None))
    return form.form[property] if form else None


class BirthPlace(AddCalculator):
    """Abstract"""

    window = A_MONTH

    def __init__(self, at, window=None):
        super(BirthPlace, self).__init__(window=window)
        self.at = at if not isinstance(at, six.string_types) else (at,)

    @fluff.filter_by
    def correct_birthplace(self, case):
        return getattr(case, 'birth_place', None) in self.at

    @fluff.date_emitter
    def total(self, case):
        yield get_add(case)


class VisitedQuickly(DoneDueCalculator, AddCalculator):
    """Abstract (though usable as is)"""
    visited_window = A_DAY

    @fluff.date_emitter
    def numerator(self, case):
        visit_time = _get_time_of_visit_after_birth(case)
        time_birth = _get_tob(case)
        if visit_time and time_birth:
            if time_birth < visit_time < time_birth + self.visited_window:
                # matches total, so you know this will be a subset of those
                yield get_add(case)

    @fluff.date_emitter
    def total(self, case):
        yield get_add(case)


class VisitedQuicklyBirthPlace(VisitedQuickly, BirthPlace):
    pass


class LiveBirthCalculator(CaseCalculator):
    """Abstract"""

    @fluff.filter_by
    def live_birth(self, case):
        return (
            get_related_prop(case, 'birth_status') == "live_birth" or
            get_related_prop(case, 'where_born') is not None
        )


class BreastFedBirthPlace(DoneDueCalculator, BirthPlace, LiveBirthCalculator):

    @fluff.date_emitter
    def numerator(self, case):
        dtf = _get_prop_from_forms(case, 'date_time_feed')
        tob = get_related_prop(case, 'time_of_birth')
        if dtf and tob:
            if dtf - tob <= datetime.timedelta(hours=1):
                yield case.add


class LiveBirthPlace(DoneDueCalculator, BirthPlace, LiveBirthCalculator):

    def correct_birthplace(self, case):
        """
        don't filter by this because total is ALL live births

        this is relying on an implementation detail of fluff:
        only the name 'correct_birthplace' is stored in the list of filters
        so this function, and not the original decorated function, is called

        """
        return True

    @fluff.date_emitter
    def numerator(self, case):
        if super(LiveBirthPlace, self).correct_birthplace(case):
            yield case.add
