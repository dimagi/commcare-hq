from __future__ import absolute_import, unicode_literals

from datetime import datetime, timedelta

import attr


@attr.s
class Month(object):
    """
    Utility class for working with months.
    """
    year = attr.ib()
    month = attr.ib()

    @property
    def start(self):
        """The very beginning of the month"""
        return datetime(self.year, self.month, 1)

    @property
    def end(self):
        """The end of the month, non-inclusive (aka the beginning of the next month)"""
        day = self.start + timedelta(days=32)
        return datetime(day.year, day.month, 1)

    def get_previous_month(self):
        day = self.start - timedelta(days=1)
        return Month.datetime_to_month(day)

    def get_next_month(self):
        return Month.datetime_to_month(self.end)

    @classmethod
    def datetime_to_month(cls, dt):
        return cls(dt.year, dt.month)

    @classmethod
    def current_month(cls):
        return cls.datetime_to_month(datetime.now())
