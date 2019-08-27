
from abc import ABCMeta, abstractproperty, abstractmethod
from datetime import datetime, timedelta

import attr
import six


class TimePeriod(six.with_metaclass(ABCMeta, object)):
    """
    Base class for providing a time period interface
    """
    @abstractproperty
    def start(self):
        pass

    @abstractproperty
    def end(self):
        pass

    @abstractmethod
    def get_previous_period(self):
        pass

    @abstractmethod
    def get_next_period(self):
        pass

    @abstractmethod
    def from_datetime(cls, dt):
        """
        This is intended to be a classmethod!
        :return: a TimePeriod object associated with the passed in date
        """
        pass

    @abstractmethod
    def current_period(cls):
        """
        This is intended to be a classmethod!
        :return: The current TimePeriod
        """
        pass


@attr.s
class Month(TimePeriod):
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

    def get_previous_period(self):
        day = self.start - timedelta(days=1)
        return Month.from_datetime(day)

    def get_next_period(self):
        return Month.from_datetime(self.end)

    @classmethod
    def from_datetime(cls, dt):
        return cls(dt.year, dt.month)

    @classmethod
    def current_period(cls):
        return cls.from_datetime(datetime.now())


@attr.s
class Week(TimePeriod):
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

    def get_previous_period(self):
        return Week.from_datetime(self.start - timedelta(days=7))

    def get_next_period(self):
        return Week.from_datetime(self.end)

    @classmethod
    def from_datetime(cls, dt):
        year, week, day = dt.isocalendar()
        return cls(year, week)

    @classmethod
    def current_period(cls):
        return cls.from_datetime(datetime.now())


def iso_year_start(iso_year):
    """
    The gregorian calendar date of the first day of the given ISO year.
    Stolen from https://stackoverflow.com/a/1700069/8207
    """
    fourth_jan = datetime(iso_year, 1, 4)
    delta = timedelta(fourth_jan.isoweekday() - 1)
    return fourth_jan - delta


def iso_to_gregorian(iso_year, iso_week, iso_day):
    """
    Gregorian calendar date for the given ISO year, week and day
    Stolen from https://stackoverflow.com/a/1700069/8207
    """
    year_start = iso_year_start(iso_year)
    return year_start + timedelta(days=iso_day - 1, weeks=iso_week - 1)
