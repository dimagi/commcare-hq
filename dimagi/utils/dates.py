from datetime import date, datetime, timedelta, time
from calendar import month_name
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
    months = months - 1 # 0 index months coming in
    nextmonths = months + offset
    months_offset = nextmonths % 12 + 1 # 1 index it going out
    years_offset = nextmonths / 12
    return (year + years_offset, months_offset)

def delta_secs(td):
    """convert a timedelta to seconds"""
    return 86400. * td.days + td.seconds + 1.0e-6 * td.microseconds


DEFAULT_DATE_FORMAT = "%m/%d/%Y"
    
class DateSpan(object):
    """
    A useful class for representing a date span
    """
    
    def __init__(self, startdate, enddate, format=DEFAULT_DATE_FORMAT, inclusive=True):
        self.startdate = startdate
        self.enddate = enddate
        self.format = format
        self.inclusive = inclusive
        self.is_default = False
    
    @property
    def startdate_param(self):
        if self.startdate:
            return self.startdate.strftime(self.format)

    @property
    def startdate_display(self):
        if self.startdate:
            return self.startdate.strftime(self.format)

    @property
    def enddate_param(self):
        if self.enddate:
            # you need to add a day to enddate if your dates are meant to be inclusive
            offset = timedelta(days=1 if self.inclusive else 0)
            return (self.enddate + offset).strftime(self.format)

    @property
    def end_of_end_day(self):
        if self.enddate:
            # if we are doing a 'day' query, we want to make sure 
            # the end date is the last second of the end day
            return self.enddate.replace(hour=23, minute=59, second=59, microsecond=1000000-1)

    @property
    def enddate_display(self):
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
    def since(cls, days, enddate=None, format=DEFAULT_DATE_FORMAT):
        """
        Generate a DateSpan ending with a certain date, and going back 
        N days. The enddate defaults to tomorrow midnight 
        (so it's inclusive of today).
        
        Will always ignore times.
        """
        if enddate is None:
            enddate = datetime.utcnow()
        end = datetime(enddate.year, enddate.month, enddate.day)
        start = end - timedelta(days=days)
        return DateSpan(start, end, format)
                    
    
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
    r = rrule(MONTHLY, byweekday=(MO, TU, WE, TH, FR), 
              dtstart=datetime(year,month, 1))
    res = r.after(datetime(year, month, day), inc=True)
    if (res == None or res.month != month or res.year != year):
        raise ValueError("No dates found in range. is there a flaw in your logic?")
    return res.date()

def get_business_day_of_month_before(year, month, day):
    """
    For a given month get the business day of the month 
    that falls on or before the passed in day
    """
    r = rrule(MONTHLY, byweekday=(MO, TU, WE, TH, FR), 
              dtstart=datetime(year,month,1))
    res = r.before(datetime(year, month, day), inc=True)
    if (res == None or res.month != month or res.year != year):
        raise ValueError("No dates found in range. is there a flaw in your logic?")
    return res.date()
