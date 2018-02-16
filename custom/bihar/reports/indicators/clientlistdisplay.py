from __future__ import absolute_import
from custom.bihar.calculations.utils.filters import get_add, get_edd
import datetime
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from . import display
from custom.bihar.reports.indicators.display import days_overdue


class ClientListDisplay(object):
    """
    Helper for generating client list table
    """

    sort_index = [0, 'asc']

    def get_columns(self):
        raise NotImplementedError("Override this!")

    def as_row(self, case, context, fluff_row):
        raise NotImplementedError("Override this!")

    def sortkey(self, case, context):
        # not having a sortkey shouldn't raise an exception so just
        # default to something reasonable
        return case.name


class SummaryValueMixIn(ClientListDisplay):
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

    @property
    def sort_index_dir(self):
        return 'asc' if _(self.numerator_text) < _(self.denominator_text) else 'desc'

    @property
    def sort_index(self):
        return [self.sort_index_i, self.sort_index_dir]

    def summary_value_raw(self, case, context):
        if display.in_numerator(case, context):
            return 'num'
        elif display.in_denominator(case, context):
            return 'denom'
        else:
            return 'neither'

    def summary_value(self, case, context):
        raw = self.summary_value_raw(case, context)
        return self._summary_display(raw)

    def _summary_display(self, raw_value):
        display = {
            'num': self.numerator_text,
            'denom': self.denominator_text,
            'neither': self.neither_text,
        }[raw_value]
        return _(display)


class PreDeliveryCLD(ClientListDisplay):
    """
    Meant to be used with IndicatorCalculators shared defaults for stuff that
    shows up in the client list.
    """

    sort_index = [2, 'desc']

    def get_columns(self):
        return _("Name"), _("Husband's Name"), _("EDD")

    def as_row(self, case, context, fluff_row):
        return (
            case.name,
            display.husband_name(case),
            display.edd(case),
        )

    def sortkey(self, case, context):
        return get_edd(case) or datetime.datetime.max.date()


class PreDeliverySummaryCLD(PreDeliveryCLD, SummaryValueMixIn):

    sort_index_i = 2

    def get_columns(self):
        return _("Name"), _("Husband's Name"), _(self.summary_header), _("EDD")

    def as_row(self, case, context, fluff_row):
        return (
            case.name,
            display.husband_name(case),
            self.summary_value(case, context),
            display.edd(case),
        )


class PostDeliveryCLD(ClientListDisplay):

    sort_index = [2, 'asc']

    def get_columns(self):
        return _("Name"), _("Husband's Name"), _("ADD")

    def as_row(self, case, context, fluff_row):
        return (
            case.name,
            display.husband_name(case),
            display.add(case),
        )

    def sortkey(self, case, context):
        # hacky way to sort by reverse add
        return datetime.datetime.today().date() - (get_add(case) or datetime.datetime.max.date())


class PostDeliverySummaryCLD(PostDeliveryCLD, SummaryValueMixIn):

    sort_index_i = 3

    def get_columns(self):
        return _("Name"), _("Husband's Name"), _(self.summary_header), _("ADD")

    def as_row(self, case, context, fluff_row):
        return (
            case.name,
            display.husband_name(case),
            self.summary_value(case, context),
            display.add(case),
        )


class DoneDueMixIn(SummaryValueMixIn):
    summary_header = ugettext_noop("Visit Status")
    numerator_text = ugettext_noop("Done")
    denominator_text = ugettext_noop("Due")

    def sortkey(self, case, context):
        return display.in_numerator(case, context)

    def _get_days_due(self, case, value, fluff_row):
        if value == 'denom':
            return fluff_row['key'][-1]  # the last item of the key is the date
        else:
            return days_overdue(case)


class PreDeliveryDoneDueCLD(DoneDueMixIn, PreDeliverySummaryCLD):

    def get_columns(self):
        return super(PreDeliveryDoneDueCLD, self).get_columns() + (_('Days Late'),)

    def as_row(self, case, context, fluff_row):
        value = 'num' if fluff_row['in_num'] else 'denom'
        return (
            case.name,
            display.husband_name(case),
            self._summary_display(value),
            display.edd(case),
            self._get_days_due(case, value, fluff_row),
        )


class PostDeliveryDoneDueCLD(DoneDueMixIn, PostDeliverySummaryCLD):
    user_hack = None

    def get_columns(self):
        return super(PostDeliveryDoneDueCLD, self).get_columns() + (_('Days Due'),)

    def as_row(self, case, context, fluff_row):
        value = 'num' if fluff_row['in_num'] else 'denom'
        return (
            case.name,
            display.husband_name(case),
            self._summary_display(value),
            display.add(case),
            self._get_days_due(case, value, fluff_row),
        )


class ComplicationsCalculator(PostDeliverySummaryCLD):

    def __init__(self, days):
        self.days = datetime.timedelta(days=days)

    @property
    def summary_header(self):
        if self.days.days > 1:
            return _("Identified in %s days") % self.days.days
        else:
            return _("Identified in %s hours") % (self.days.days*24)
