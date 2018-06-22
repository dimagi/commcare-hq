from __future__ import absolute_import
from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod, abstractproperty
from functools import total_ordering

import six

from corehq.apps.aggregate_ucrs.date_utils import Month
from dimagi.utils.parsing import json_format_date

AGGREGATION_UNIT_CHOICE_MONTH = 'month'

AGG_WINDOW_START_PARAM = 'agg_window_start'
AGG_WINDOW_END_PARAM = 'agg_window_end'


class TimeAggregationWindow(six.with_metaclass(ABCMeta, object)):
    """
    Base class for holding a time-based aggregation window.
    Should deal with conversion of a period into start/end dates, equality checks
    and getting the next window from an existing window.
    """

    def __init__(self, datetime):
        self._datetime = datetime

    @classmethod
    def from_aggregation_unit(cls, unit):
        adapter_classes = {
            AGGREGATION_UNIT_CHOICE_MONTH: MonthAggregationWindow
        }
        return adapter_classes[unit]

    @abstractmethod
    def next_window(self):
        pass

    @abstractproperty
    def start(self):
        """
        :return: the start of the window as a datetime
        """
        pass

    @property
    def start_param(self):
        """
        :return: the start of the window as a string (to be used in SQL)
        """
        return json_format_date(self.start)

    @abstractproperty
    def end(self):
        """
        :return: the end of the window as a datetime
        """
        pass

    @property
    def end_param(self):
        """
        :return: the end of the window as a string (to be used in SQL)
        """
        return json_format_date(self.end)

    def __str__(self):
        return '{}: {}-{}'.format(type(self).__name__, self.start, self.end)


@total_ordering
class MonthAggregationWindow(six.with_metaclass(ABCMeta, TimeAggregationWindow)):
    """
    An aggregation window based on months.
    """

    def next_window(self):
        return MonthAggregationWindow(self._month.end)

    @property
    def start(self):
        return self._month.start

    @property
    def end(self):
        return self._month.end

    def __init__(self, datetime):
        super(MonthAggregationWindow, self).__init__(datetime)
        self._month = Month.from_datetime(self._datetime)

    def __eq__(self, other):
        return isinstance(other, MonthAggregationWindow) and self._month == other._month

    def __hash__(self):
        return hash((type(self), self.start))

    def __lt__(self, other):
        return self._month < other._month
