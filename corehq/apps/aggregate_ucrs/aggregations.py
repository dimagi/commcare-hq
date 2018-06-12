from __future__ import absolute_import
from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod, abstractproperty
from functools import total_ordering

import six

from corehq.apps.aggregate_ucrs.date_utils import Month

AGGREGATION_UNIT_CHOICE_MONTH = 'month'

AGG_WINDOW_START_PARAM = 'agg_window_start'
AGG_WINDOW_END_PARAM = 'agg_window_end'


class TimeAggregation(six.with_metaclass(ABCMeta, object)):

    def __init__(self, datetime):
        self._datetime = datetime

    @classmethod
    def from_aggregation_unit(cls, unit):
        adapter_classes = {
            AGGREGATION_UNIT_CHOICE_MONTH: MonthAggregation
        }
        return adapter_classes[unit]

    @abstractmethod
    def next_window(self):
        pass

    @abstractproperty
    def start(self):
        pass

    @abstractproperty
    def end(self):
        pass

    def __str__(self):
        return '{}: {}-{}'.format(type(self).__name__, self.start, self.end)


@total_ordering
class MonthAggregation(six.with_metaclass(ABCMeta, TimeAggregation)):

    def next_window(self):
        return MonthAggregation(self._month.end)

    @property
    def start(self):
        return self._month.start

    @property
    def end(self):
        return self._month.end

    def __init__(self, datetime):
        super(MonthAggregation, self).__init__(datetime)
        self._month = Month.datetime_to_month(self._datetime)

    def __eq__(self, other):
        return self._month == other._month

    def __lt__(self, other):
        return self._month < other._month
