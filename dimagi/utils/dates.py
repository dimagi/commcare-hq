from datetime import date, datetime, timedelta, time
from dimagi.utils.logging import log_exception
from dimagi.utils.parsing import string_to_datetime

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
    
    def __init__(self, startdate, enddate, format=DEFAULT_DATE_FORMAT):
        self.startdate = startdate
        self.enddate = enddate
        self.format = format
    
    @property
    def startdate_param(self):
        if self.startdate:
            return self.startdate.strftime(self.format)
    
    @property
    def enddate_param(self):
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
        
        # if the end date is today or tomorrow, use "last N days syntax"  
        today = datetime.combine(datetime.today(), time())
        day_after_tomorrow = today + timedelta (days=2)
        if today <= self.enddate < day_after_tomorrow:
            return "last %s days" % (self.enddate - self.startdate).days 
        
        return "%s to %s" % (self.startdate.strftime(self.format), 
                             self.enddate.strftime(self.format))
        
    @classmethod
    def since(cls, days, enddate=None, format=DEFAULT_DATE_FORMAT):
        """
        Generate a DateSpan ending with a certain date, and going back 
        N days. The enddate defaults to tomorrow midnight 
        (so it's inclusive of today).
        
        Will always ignore times.
        """
        if enddate is None:
            enddate = datetime.utcnow() + timedelta(days=1)
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
        
