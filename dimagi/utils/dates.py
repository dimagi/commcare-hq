from datetime import date, datetime, timedelta, time
from calendar import month_name
try:
    # < 3.0
    from celery.log import get_task_logger
except ImportError:
    # >= 3.0
    from celery.utils.log import get_task_logger
import dateutil
import pytz
from dimagi.utils.logging import log_exception
from dimagi.utils.parsing import string_to_datetime
from dateutil.rrule import *

def force_to_date(val):
    """Forces a date, string, or datetime to a date."""
    if not val:                      return val
    if isinstance(val, datetime):    return val.date()
    if isinstance(val, date):        return val
    if isinstance(val, basestring):  return string_to_datetime(val).date()
    else:                            raise ValueError("object must be date or datetime!")
    
def force_to_datetime(val):
    """Forces a date, string, or datetime to a datetime."""
    if not val:                        return val
    elif isinstance(val, datetime):    return val
    elif isinstance(val, date):        return datetime.combine(val, time())
    elif isinstance(val, basestring):  return string_to_datetime(val)
    else:                              raise ValueError("object must be date or datetime!")    
        
def safe_date_add(startdate, days, force_to_date_flag=True):
    if not startdate:  return None
    try: 
        val = startdate + timedelta(days)
        if force_to_date_flag:  return force_to_date(val)
        else:                   return val 
    except OverflowError, e:
        log_exception(e) 
        return None

def months_between(start, end):
    """
    Given a start date and enddate return all months between them.
    Returns a list of (Year, month) tuples, the first one being
    the year and month of the start date, and the last one being
    the year and month of the end date.
    """
    assert(start <= end)
    months = []
    while start <= end:
        months.append((start.year, start.month))
        (yearnext, monthnext) = add_months(start.year, start.month, 1)
        start = datetime(yearnext, monthnext, 1)
    return months        

def add_months(year, months, offset):
    """
    Add a number of months to the passed in year and month, returning
    a tuple of (year, month)
    """
    months = months - 1 # 0 index months coming in
    nextmonths = months + offset
    months_offset = nextmonths % 12 + 1 # 1 index it going out
    years_offset = nextmonths / 12
    return (year + years_offset, months_offset)

def first_of_next_month(ref_date):
    """
    Given a datetime, return a datetime that is the first of the following
    month.
    """
    year, month = add_months(ref_date.year, ref_date.month, 1)
    return datetime(year, month, 1)

def delta_secs(td):
    """convert a timedelta to seconds"""
    return 86400. * td.days + td.seconds + 1.0e-6 * td.microseconds

def secs_to_days(seconds):
    """convert a number of seconds to days"""
    return float(seconds) / 86400. 


def utcnow_sans_milliseconds():
    return datetime.utcnow().replace(microsecond=0)
    
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
    
class DateSpan(object):
    """
    A useful class for representing a date span
    """
    startdate = None
    enddate = None
    format = None
    inclusive = True
    is_default = False
    
    def __init__(self, startdate, enddate, format=DEFAULT_DATE_FORMAT, inclusive=True, timezone=pytz.utc):
        self.startdate = startdate
        self.enddate = enddate
        self.format = format
        self.inclusive = inclusive
        self.timezone = timezone

    def __getstate__(self):
        """
            For pickling the DateSpan object.
        """
        return dict(
            startdate=self.startdate.isoformat(),
            enddate=self.enddate.isoformat(),
            format=self.format,
            inclusive=self.inclusive,
            is_default=self.is_default,
            timezone=self.timezone.zone
        )

    def __setstate__(self, state):
        """
            For un-pickling the DateSpan object.
        """
        logging = get_task_logger(__name__) # logging is likely to happen within celery
        try:
            self.startdate = dateutil.parser.parse(state.get('startdate'))
            self.enddate = dateutil.parser.parse(state.get('enddate'))
        except Exception as e:
            logging.error("Could not unpack start and end dates for DateSpan. Error: %s" % e)
        self.format = state.get('format', DEFAULT_DATE_FORMAT)
        self.inclusive = state.get('inclusive', True)
        self.timezone = pytz.utc
        self.is_default = state.get('is_default', False)
        try:
            self.timezone = pytz.timezone(state.get('timezone'))
        except Exception as e:
            logging.error("Could not unpack timezone for DateSpan. Error: %s" % e)


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
            offset = timedelta(days=1 if self.inclusive else 0)
            return (self.enddate + offset)
        
    
    @property
    def startdate_param(self):
        """
        This is used for couch queries to get the adjusted date as a string
        that can be easily used in a couch view.
        """
        if self.startdate:
            return self.startdate.strftime(self.format)

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
    def enddate_param(self):
        if self.enddate:
            # you need to add a day to enddate if your dates are meant to be inclusive
            offset = timedelta(days=1 if self.inclusive else 0)
            return (self.enddate + offset).strftime(self.format)

    @property
    def enddate_utc(self):
        if self.enddate:
            adjusted_enddate = self.adjust_to_utc(self.enddate)
            # you need to add a day to enddate if your dates are meant to be inclusive
            adjusted_enddate = (adjusted_enddate + timedelta(days=1 if self.inclusive else 0))
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
        return date - timedelta(hours=int(offset[0:3]), minutes=int(offset[0] + offset[3:5]))

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
            return "You have to specify both dates!"
        else:
            if self.enddate < self.startdate:
                return "You can't have an end date of %s after start date of %s" % (self.enddate, self.startdate)
        return ""
    
    def __str__(self):
        if not self.is_valid():
            return "Invalid date span %s - %s" % (self.startdate_param, self.enddate_param)

        # if the dates comprise a month exactly, use that
        if self.startdate.day == 1 and (self.enddate + timedelta(days=1)).day == 1:
            return "%s %s" % (month_name[self.startdate.month], self.startdate.year)

        # if the end date is today or tomorrow, use "last N days syntax"  
        today = datetime.combine(datetime.today(), time())
        day_after_tomorrow = today + timedelta (days=2)
        if today <= self.enddate < day_after_tomorrow:
            return "last %s days" % (self.enddate - self.startdate).days
        
        return "%s to %s" % (self.startdate.strftime(self.format), 
                             self.enddate.strftime(self.format))
        
    @classmethod
    def month(cls, year, month, format=DEFAULT_DATE_FORMAT):
        """
        Generate a datespan covering a month.
        """
        start = datetime(year, month, 1)
        nextmonth = start + timedelta(days=32)
        end = datetime(nextmonth.year, nextmonth.month, 1) - timedelta(milliseconds=1)
        return DateSpan(start, end, format)
    
    @classmethod
    def since(cls, days, enddate=None, format=DEFAULT_DATE_FORMAT, inclusive=True, timezone=pytz.utc):
        """
        Generate a DateSpan ending with a certain date, and going back 
        N days. The enddate defaults to today midnight but is inclusive
        (which means it will look like tomorrow midnight)
        
        Will always ignore times.
        """
        if enddate is None:
            enddate = datetime.now(tz=timezone) 
        end = datetime(enddate.year, enddate.month, enddate.day)
        start = end - timedelta(days=days)
        return DateSpan(start, end, format, inclusive, timezone)
                    
    
    def parse(self, startdate_str, enddate_str, parse_format, display_format=None):
        """
        Generate a DateSpan with string formats. 
        """
        if display_format is None:
            display_format = format
        
        def date_or_nothing(param):
            return datetime.strptime(dict[param], parse_format)\
                        if param in dict and dict[param] else None
        startdate = date_or_nothing(startdate_str)
        enddate = date_or_nothing(enddate_str)
        return DateSpan(startdate, enddate, format)

    def months_iterator(self):
        """
        Iterate over (year, month) pairs (inclusive) in this datespan.
        """
        for year in range(self.startdate.year, self.enddate.year + 1):
            startmonth = 1
            endmonth = 12
            if year == int(self.startdate.year):
                startmonth = self.startdate.month
            if year == int(self.enddate.year):
                endmonth = self.enddate.month
            for month in range(startmonth, endmonth + 1):
                yield (year, month)

def is_business_day(day):
    """
    Simple method to whether something is a business day, assumes M-F working
    days.
    """
    return day.weekday() < 5
    
def get_day_of_month(year, month, count):
    """
    For a given month get the Nth day.
    The only reason this function exists in favor of 
    just creating the date object is to support negative numbers
    e.g. pass in -1 for "last"
    """
    r = rrule(MONTHLY, dtstart=datetime(year,month, 1),
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
              dtstart=datetime(year,month, 1),
              bysetpos=count)
    res = r[0]
    if (res == None or res.month != month or res.year != year):
        raise ValueError("No dates found in range. is there a flaw in your logic?")
    return res.date()

def get_business_day_of_month_after(year, month, day):
    """
    For a given month get the business day of the month 
    that falls on or after the passed in day
    """
    try:
        adate = datetime(year, month, day)
    except ValueError:
        try:
            adate = datetime(year, month, 30)
        except ValueError:
            try:
                adate = datetime(year, month, 29)
            except ValueError:
                adate = datetime(year, month, 28)
    r = rrule(MONTHLY, byweekday=(MO, TU, WE, TH, FR), 
              dtstart=datetime(year,month, 1))
    res = r.after(adate, inc=True)
    if (res == None or res.month != month or res.year != year):
        raise ValueError("No dates found in range. is there a flaw in your logic?")
    return res.date()

def get_business_day_of_month_before(year, month, day):
    """
    For a given month get the business day of the month 
    that falls on or before the passed in day
    """
    try:
        adate = datetime(year, month, day)
    except ValueError:
        try:
            adate = datetime(year, month, 30)
        except ValueError:
            try:
                adate = datetime(year, month, 29)
            except ValueError:
                adate = datetime(year, month, 28)
    r = rrule(MONTHLY, byweekday=(MO, TU, WE, TH, FR), 
              dtstart=datetime(year,month,1))
    res = r.before(adate, inc=True)
    if (res == None or res.month != month or res.year != year):
        raise ValueError("No dates found in range. is there a flaw in your logic?")
    return res.date()
