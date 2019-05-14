from __future__ import absolute_import
from __future__ import unicode_literals
from functools import total_ordering

from corehq.apps.aggregate_ucrs.date_utils import Month, Week
from dimagi.utils.parsing import json_format_date

AGGREGATION_UNIT_CHOICE_MONTH = 'month'
AGGREGATION_UNIT_CHOICE_WEEK = 'week'

AGG_WINDOW_START_PARAM = 'agg_window_start'
AGG_WINDOW_END_PARAM = 'agg_window_end'


def get_time_period_class(aggregation_unit):
    return {
        AGGREGATION_UNIT_CHOICE_MONTH: Month,
        AGGREGATION_UNIT_CHOICE_WEEK: Week,
    }[aggregation_unit]


@total_ordering
class TimePeriodAggregationWindow(object):
    """
    Class for holding a time-based aggregation window based on a TimePeriod.
    Should deal with conversion of a period into start/end dates, equality checks
    and getting the next window from an existing window.
    """

    def __init__(self, period_class, datetime_):
        self._datetime = datetime_
        self._period_class = period_class
        self._period = period_class.from_datetime(self._datetime)

    def next_window(self):
        return TimePeriodAggregationWindow(self._period_class, self._period.end)

    @property
    def start(self):
        return self._period.start

    @property
    def end(self):
        return self._period.end

    @property
    def start_param(self):
        """
        :return: the start of the window as a string (to be used in SQL)
        """
        return json_format_date(self.start)

    @property
    def end_param(self):
        """
        :return: the end of the window as a string (to be used in SQL)
        """
        return json_format_date(self.end)

    def __str__(self):
        return '{}: {}-{}'.format(type(self).__name__, self.start, self.end)

    def __eq__(self, other):
        return isinstance(other, TimePeriodAggregationWindow) and self._period == other._period

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((type(self), self.start))

    def __lt__(self, other):
        return self._period < other._period
