from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import datetime
from calendar import month_name
from django.utils.translation import ugettext_lazy as _
import logging
import six

try:
    # < 3.0
    from celery.log import get_task_logger
except ImportError:
    # >= 3.0
    from celery.utils.log import get_task_logger
import dateutil
import pytz
from dimagi.utils.parsing import string_to_datetime, ISO_DATE_FORMAT
from dateutil.rrule import *


def force_to_date(val):
    """Forces a date, string, or datetime to a date."""
    if not val:
        return val
    elif isinstance(val, datetime.datetime):
        return val.date()
    elif isinstance(val, datetime.date):
        return val
    elif isinstance(val, six.string_types):
        from corehq.util.python_compatibility import soft_assert_type_text
        soft_assert_type_text(val)
        return string_to_datetime(val).date()
    else:
        raise ValueError("object must be date or datetime!")


def force_to_datetime(val):
    """Forces a date, string, or datetime to a datetime."""
    if not val:
        return val
    elif isinstance(val, datetime.datetime):
        return val
    elif isinstance(val, datetime.date):
        return datetime.datetime.combine(val, datetime.time())
    elif isinstance(val, six.string_types):
        from corehq.util.python_compatibility import soft_assert_type_text
        soft_assert_type_text(val)
        return string_to_datetime(val)
    else:
        raise ValueError("object must be date or datetime!")


def months_between(start, end):
    """
    Given a start date and enddate return all months between them.
    Returns a list of (Year, month) tuples, the first one being
    the year and month of the start date, and the last one being
    the year and month of the end date.
    """
    assert datetime.date(start.year, start.month, 1) <= datetime.date(end.year, end.month, 1), \
        'start date {} was later than end date {}!'.format(start, end)
    months = []
    date_type = type(start)
    while start <= end:
        months.append((start.year, start.month))
        (yearnext, monthnext) = add_months(start.year, start.month, 1)
        start = date_type(yearnext, monthnext, 1)
    return months        


def add_months(year, months, offset):
    """
    Add a number of months to the passed in year and month, returning
    a tuple of (year, month)
    """
    months = months - 1  # 0 index months coming in
    nextmonths = months + offset
    months_offset = nextmonths % 12 + 1  # 1 index it going out
    years_offset = nextmonths // 12
    return (year + years_offset, months_offset)


def add_months_to_date(date_or_datetime, offset):
    """
    Adds an offset of months to a date or datetime object.
    """
    newyear, newmonth = add_months(date_or_datetime.year, date_or_datetime.month, offset)
    try:
        return date_or_datetime.replace(year=newyear, month=newmonth)
    except ValueError:
        ret = date_or_datetime.replace(year=newyear, month=newmonth, day=1)
        return ret.replace(day=(first_of_next_month(ret) - datetime.timedelta(days=1)).day)


def first_of_next_month(ref_date):
    """
    Given a datetime, return a datetime that is the first of the following
    month.
    """
    year, month = add_months(ref_date.year, ref_date.month, 1)
    return type(ref_date)(year, month, 1)


def utcnow_sans_milliseconds():
    return datetime.datetime.utcnow().replace(microsecond=0)


def today_or_tomorrow(date, inclusive=True):
    today = datetime.datetime.combine(datetime.datetime.today(), datetime.time())
    if type(date) == datetime.date:
        today = today.date()
    day_after_tomorrow = today + datetime.timedelta(days=2)

    return today <= date + datetime.timedelta(days=1 if inclusive else 0) < day_after_tomorrow


class DateSpan(object):
    """
    A useful class for representing a date span
    """
    startdate = None
    enddate = None
    format = None
    inclusive = True
    is_default = False
    _max_days = None

    def __init__(self, startdate, enddate, format=ISO_DATE_FORMAT, inclusive=True, timezone=pytz.utc,
                 max_days=None):
        self.startdate = startdate
        self.enddate = enddate
        self.format = format
        self.inclusive = inclusive
        self.timezone = timezone
        self.max_days = max_days

    def __getstate__(self):
        """
            For pickling the DateSpan object.
        """
        return dict(
            startdate=self.startdate.isoformat() if self.startdate else None,
            enddate=self.enddate.isoformat() if self.enddate else None,
            format=self.format,
            inclusive=self.inclusive,
            is_default=self.is_default,
            timezone=self.timezone.zone,
            max_days=self.max_days,
        )

    def __setstate__(self, state):
        """
            For un-pickling the DateSpan object.
        """
        logging = get_task_logger(__name__) # logging is likely to happen within celery
        try:
            self.startdate = dateutil.parser.parse(state.get('startdate')) if state.get('startdate') else None
            self.enddate = dateutil.parser.parse(state.get('enddate')) if state.get('enddate') else None
        except Exception as e:
            logging.error("Could not unpack start and end dates for DateSpan. Error: %s" % e)
        self.format = state.get('format', ISO_DATE_FORMAT)
        self.inclusive = state.get('inclusive', True)
        self.timezone = pytz.utc
        self.is_default = state.get('is_default', False)
        self.max_days = state.get('max_days')
        try:
            self.timezone = pytz.timezone(state.get('timezone'))
        except Exception as e:
            logging.error("Could not unpack timezone for DateSpan. Error: %s" % e)

    @property
    def max_days(self):
        return self._max_days

    @max_days.setter
    def max_days(self, value):
        if value is not None and value < 0:
            raise ValueError('max_days cannot be less than 0')
        self._max_days = value

    def to_dict(self):
        return {
            'startdate': self.startdate,
            'enddate': self.enddate
        }

    @classmethod
    def from_dict(cls, data):
        return cls(string_to_datetime(data['startdate'], data['enddate']))

    @property
    def computed_startdate(self):
        """
        This is used for queries that need an actual date (e.g. django)
        that is computed based on the inclusive flag.
        """
        return self.startdate
        
    @property
    def computed_enddate(self):
        """
        This is used for queries that need an actual date (e.g. django)
        that is computed based on the inclusive flag.
        """
        if self.enddate:
            # you need to add a day to enddate if your dates are meant to be inclusive
            offset = datetime.timedelta(days=1 if self.inclusive else 0)
            return (self.enddate + offset)
        
    
    @property
    def startdate_param(self):
        """
        This is used for couch queries to get the adjusted date as a string
        that can be easily used in a couch view.
        """
        return self.startdate_display

    @property
    def startdate_utc(self):
        if self.startdate:
            return self.adjust_to_utc(self.startdate)

    @property
    def startdate_param_utc(self):
        if self.startdate:
            adjusted_startdate = self.adjust_to_utc(self.startdate)
            return adjusted_startdate.isoformat()

    @property
    def startdate_display(self):
        """
        This can be used in templates to regenerate this object.
        """
        if self.startdate:
            return self.startdate.strftime(self.format)

    @property
    def startdate_key_utc(self):
        utc_startdate = self.startdate_utc
        if utc_startdate:
            return [utc_startdate.year, utc_startdate.month, utc_startdate.day]
        return []

    @property
    def enddate_adjusted(self):
        if self.enddate:
            # you need to add a day to enddate if your dates are meant to be inclusive
            offset = datetime.timedelta(days=1 if self.inclusive else 0)
            return self.enddate + offset

    @property
    def enddate_param(self):
        if self.enddate:
            return self.enddate_adjusted.strftime(self.format)

    @property
    def enddate_utc(self):
        if self.enddate:
            adjusted_enddate = self.adjust_to_utc(self.enddate_adjusted)
            return adjusted_enddate

    @property
    def enddate_param_utc(self):
        if self.enddate:
            return self.enddate_utc.isoformat()

    @property
    def enddate_key_utc(self):
        utc_enddate = self.enddate_utc
        if utc_enddate:
            return [utc_enddate.year, utc_enddate.month, utc_enddate.day]
        return []

    def adjust_to_utc(self, date):
        localized = self.timezone.localize(date)
        offset = localized.strftime("%z")
        return date - datetime.timedelta(hours=int(offset[0:3]), minutes=int(offset[0] + offset[3:5]))

    @property
    def end_of_end_day(self):
        if self.enddate:
            # if we are doing a 'day' query, we want to make sure 
            # the end date is the last second of the end day
            return self.enddate.replace(hour=23, minute=59, second=59, microsecond=1000000-1)

    @property
    def enddate_display(self):
        """
        This can be used in templates to regenerate this object.
        """
        if self.enddate:
            return self.enddate.strftime(self.format)
    
    def is_valid(self):
        # this is a bit backwards but keeps the logic in one place
        return not bool(self.get_validation_reason())
    
    def get_validation_reason(self):
        if self.startdate is None or self.enddate is None:
            return _("You have to specify both dates!")
        elif self.enddate < self.startdate:
            return _("You can't have an end date of {end} after start date of {start}").format(
                end=self.enddate, start=self.startdate)
        elif self.startdate.year < 1900:
            return _("You can't use dates earlier than the year 1900")
        elif self.max_days is not None:
            delta = self.enddate - self.startdate
            if delta.days > self.max_days:
                return _("You are limited to a span of {max} days, but this date range spans {total} days").format(
                    max=self.max_days, total=delta.days)
        return ""
    
    def __str__(self):
        if not self.is_valid():
            return "Invalid date span %s - %s" % (self.startdate_param, self.enddate_param)

        # if the dates comprise a month exactly, use that
        if (self.startdate.day == 1 and
                (self.enddate + datetime.timedelta(days=1)).day == 1
                and (self.enddate - self.startdate) < datetime.timedelta(days=32)):
            return "%s %s" % (month_name[self.startdate.month], self.startdate.year)

        # if the end date is today or tomorrow, use "last N days syntax"
        if today_or_tomorrow(self.enddate, self.inclusive):
            return "last %s days" % ((self.enddate - self.startdate).days + (1 if self.inclusive else 0))
        
        return self.default_serialization()

    def __repr__(self):
        return str(self)

    def default_serialization(self):
        return "%s to %s" % (self.startdate_display,
                             self.enddate_display)

    @classmethod
    def since(cls, days, enddate=None, format=ISO_DATE_FORMAT, inclusive=True, timezone=pytz.utc):
        """
        Generate a DateSpan ending with a certain date, and starting at a date that will
        include N number of days.

        The endddate defaults to yesterday midnight for inclusive request
        (which means it will look like today midnight);
        defaults to today midnight for non inclusive requests

        e.g: enddate=7/21/2013, days=7, inclusive=True => 7/15/2013 - 7/21/2013 (15, 16, 17, 18, 19, 20, 21)
        e.g: enddate=7/21/2013, days=7, inclusive=False => 7/14/2013 - 7/21/2013 (14, 15, 16, 17, 18, 19, 20)

        Will always ignore times.
        """
        if enddate is None:
            enddate = datetime.datetime.now(tz=timezone)
            if inclusive:
                enddate = enddate - datetime.timedelta(days=1)

        if inclusive:
            days += -1

        end = datetime.datetime(enddate.year, enddate.month, enddate.day)
        start = end - datetime.timedelta(days=days)
        return DateSpan(start, end, format, inclusive, timezone)

    @classmethod
    def max(cls):
        return cls(datetime.datetime.min, datetime.datetime.max, inclusive=False)

    @classmethod
    def from_month(cls, month=None, year=None, format=ISO_DATE_FORMAT,
        inclusive=True, timezone=pytz.utc):
        """
        Generate a DateSpan object given a numerical month and year.
        Both are optional and default to the current month/year.

            april = DateSpan.from_month(04, 2013)
        """
        if month is None:
            month = datetime.date.today().month
        if year is None:
            year = datetime.date.today().year
        assert isinstance(month, int) and isinstance(year, int)
        start = datetime.datetime(year, month, 1)
        next = start + datetime.timedelta(days=32)
        end = datetime.datetime(next.year, next.month, 1) - datetime.timedelta(days=1)
        return DateSpan(start, end, format, inclusive, timezone)

    def set_timezone(self, to_tz):
        """
        Sets the dates in this object to a specific timezone. This will actually change
        the times (as opposed, to setting the timezone and adjusting the times). So
        3pm in EST will be converted to PST as 3pm (so 6pm in EST) instead of adjusting
        the time.
        """
        self.startdate = to_tz.localize(self.startdate.replace(tzinfo=None))
        self.enddate = to_tz.localize(self.enddate.replace(tzinfo=None))
        self.timezone = to_tz


def get_day_of_month(year, month, count):
    """
    For a given month get the Nth day.
    The only reason this function exists in favor of 
    just creating the date object is to support negative numbers
    e.g. pass in -1 for "last"
    """
    r = rrule(MONTHLY, dtstart=datetime.datetime(year, month, 1),
              byweekday=(MO, TU, WE, TH, FR, SA, SU),
              bysetpos=count)
    res = r[0]
    if (res == None or res.month != month or res.year != year):
        raise ValueError("No dates found in range. is there a flaw in your logic?")
    return res.date()


def get_business_day_of_month(year, month, count):
    """
    For a given month get the Nth business day by count.
    Count can also be negative, e.g. pass in -1 for "last"
    """
    r = rrule(MONTHLY, byweekday=(MO, TU, WE, TH, FR), 
              dtstart=datetime.datetime(year, month, 1),
              bysetpos=count)
    res = r[0]
    if (res == None or res.month != month or res.year != year):
        raise ValueError("No dates found in range. is there a flaw in your logic?")
    return res.date()


def get_business_day_of_month_before(year, month, day):
    """
    For a given month get the business day of the month 
    that falls on or before the passed in day
    """
    try:
        adate = datetime.datetime(year, month, day)
    except ValueError:
        try:
            adate = datetime.datetime(year, month, 30)
        except ValueError:
            try:
                adate = datetime.datetime(year, month, 29)
            except ValueError:
                adate = datetime.datetime(year, month, 28)
    r = rrule(MONTHLY, byweekday=(MO, TU, WE, TH, FR), 
              dtstart=datetime.datetime(year, month, 1))
    res = r.before(adate, inc=True)
    if (res == None or res.month != month or res.year != year):
        raise ValueError("No dates found in range. is there a flaw in your logic?")
    return res.date()


def safe_strftime(val, fmt):
    """
    conceptually the same as val.strftime(fmt), but this works even with
    dates pre-1900.

    (For some reason, '%Y' and others do not work for pre-1900 dates
    in python stdlib datetime.[date|datetime].strftime.)

    This function strictly asserts that fmt does not contain directives whose
    value is dependent on the year, such as week number of the year ('%W').
    """
    assert '%a' not in fmt  # short weekday name
    assert '%A' not in fmt  # full weekday name
    assert '%w' not in fmt  # weekday (Sun-Sat) as a number (0-6)
    assert '%U' not in fmt  # week number of the year (weeks starting on Sun)
    assert '%W' not in fmt  # week number of the year (weeks starting on Mon)
    assert '%c' not in fmt  # full date and time representation
    assert '%x' not in fmt  # date representation
    assert '%X' not in fmt  # time representation
    # important that our dummy year is a leap year
    # so that it has Feb. 29 in it
    a_leap_year = 2012
    if isinstance(val, datetime.datetime):
        safe_val = datetime.datetime(
            a_leap_year, val.month, val.day, hour=val.hour,
            minute=val.minute, second=val.second,
            microsecond=val.microsecond, tzinfo=val.tzinfo)
    else:
        safe_val = datetime.date(a_leap_year, val.month, val.day)
    return safe_val.strftime(fmt
                             .replace("%Y", str(val.year))
                             .replace("%y", str(val.year)[-2:]))
