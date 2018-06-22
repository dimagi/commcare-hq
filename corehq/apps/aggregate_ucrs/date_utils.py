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


@attr.s
class Week(object):
    """
    Utility class for working with weeks.
    """
    year = attr.ib()
    week = attr.ib()

    @property
    def start(self):
        """The beginning of the week"""
        # 0 = monday to monday. we could eventually make this configurable
        return iso_to_gregorian(self.year, self.week, 1)

    @property
    def end(self):
        """The end of the week, non-inclusive (aka the beginning of the next week)"""
        return self.start + timedelta(days=7)

    def get_previous_week(self):
        return Week.datetime_to_week(self.start - timedelta(days=7))

    def get_next_week(self):
        return Week.datetime_to_week(self.end)

    @classmethod
    def datetime_to_week(cls, dt):
        year, week, day = dt.isocalendar()
        return cls(year, week)

    @classmethod
    def current_week(cls):
        return cls.datetime_to_week(datetime.now())


def iso_year_start(iso_year):
    """
    The gregorian calendar date of the first day of the given ISO year.
    Stolen from https://stackoverflow.com/a/1700069/8207
    """
    fourth_jan = datetime(iso_year, 1, 4)
    delta = timedelta(fourth_jan.isoweekday()-1)
    return fourth_jan - delta


def iso_to_gregorian(iso_year, iso_week, iso_day):
    """
    Gregorian calendar date for the given ISO year, week and day
    Stolen from https://stackoverflow.com/a/1700069/8207
    """
    year_start = iso_year_start(iso_year)
    return year_start + timedelta(days=iso_day-1, weeks=iso_week-1)
