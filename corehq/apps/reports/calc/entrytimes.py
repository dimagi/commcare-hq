from collections import defaultdict
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from corehq.apps.reports.display import xmlns_to_name
import sys

def get_data(domain, user=None, datespan=None):
    """
    Returns a data structure like:
    
    { <Form display name>:
         { <date>: { count: <count>, 
                     max: <time in ms>, 
                     min: <time in ms>,
                     sum: <time in ms> 
                   }
         }   
    }
    """
    if datespan is None:
        datespan = DateSpan.since(days=30, format="%Y-%m-%dT%H:%M:%S")
    
    all_data = defaultdict(lambda: defaultdict(lambda: 0))
    startkey = ["udx", domain, user, datespan.startdate_param] if user \
                else ["dx", domain, datespan.startdate_param]
    endkey = ["udx", domain, user, datespan.enddate_param] if user \
                else ["dx", domain, datespan.enddate_param]
    view = get_db().view("formtrends/form_duration_by_user", 
                         startkey=startkey,
                         endkey=endkey,
                         group=True,
                         reduce=True)
    for row in view:
        date = row["key"][-2]
        xmlns = row["key"][-1]
        form_name = xmlns_to_name(xmlns, domain)
        data = all_data[form_name]
        if not date in data:
            data[date] = defaultdict(lambda: 0)
        thisrow = row["value"]
        for key, val in thisrow.items():
            data[date][key] = data[date][key] + thisrow[key]
    return all_data

def get_user_data(domain, xmlns, datespan=None):
    """
    Returns a data structure like:
    
    { <user>: { count: <count>, 
                max: <time in ms>, 
                min: <time in ms>,
                sum: <time in ms> 
              }
    }
    
    """
    if datespan is None:
        datespan = DateSpan.since(days=30, format="%Y-%m-%dT%H:%M:%S")
    
    all_data = {}
    startkey = ["xdu", domain, xmlns, datespan.startdate_param] 
    endkey = ["xdu", domain, xmlns, datespan.enddate_param]
    view = get_db().view("formtrends/form_duration_by_user", 
                         startkey=startkey,
                         endkey=endkey,
                         group=True,
                         reduce=True)
    for row in view:
        user = row["key"][4]
        if not user in all_data:
            all_data[user] = {"count": 0, "min": sys.maxint, "max": 0, "sum": 0}
        xmlns = row["key"][2]
        thisrow = row["value"]
        all_data[user]["count"] = all_data[user]["count"] + thisrow["count"]
        all_data[user]["sum"] = all_data[user]["sum"] + thisrow["sum"]
        all_data[user]["min"] = min(all_data[user]["min"], thisrow["min"])
        all_data[user]["max"] = max(all_data[user]["max"], thisrow["max"])
    
    return all_data
