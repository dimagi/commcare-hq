from datetime import datetime, date, time
from dateutil.parser import parse

TRUE_STRINGS = ("true", "t", "yes", "y")
FALSE_STRINGS = ("false", "f", "no", "n")

def string_to_boolean(val):
    """
    A very dumb string to boolean converter.  Will fail hard
    if the conversion doesn't succeed.
    """
    if val is None: return False
    if isinstance(val, bool):
        return val
    if val.lower().strip() in TRUE_STRINGS:
        return True
    elif val.lower().strip() in FALSE_STRINGS:
        return False
    raise ValueError("%s is not a parseable boolean!" % val)
    
def string_to_datetime(val):
    """
    Try to convert a string to a date.  
    """
    # python dateutil gives this to us out of the box, but it's convenient to be able
    # to reference it here.  
    if isinstance(val, datetime):
        return val
    elif isinstance(val, date):
        return datetime.combine(val, time())
    return parse(val)
    
# some date to json tricks from 
# http://stackoverflow.com/questions/455580/json-datetime-between-python-and-javascript
ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
def json_format_datetime(time):
    return time.strftime(ISO_FORMAT)

ISO_DATE_FORMAT = '%Y-%m-%d'
def json_format_date(time):
    return time.strftime(ISO_DATE_FORMAT)


ISO_MIN = datetime(1900, 1, 1)

# use: json.dumps(datetime.datetime.now(), default=json_dt_handler)
json_dt_handler = lambda obj: obj.isoformat() if isinstance(obj, datetime.datetime) else None