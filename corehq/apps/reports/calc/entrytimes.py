from collections import defaultdict
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from corehq.apps.reports.display import xmlns_to_name

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
        form_name = xmlns_to_name(domain, xmlns, app_id=None)
        data = all_data[form_name]
        if not date in data:
            data[date] = defaultdict(lambda: 0)
        thisrow = row["value"]
        for key, val in thisrow.items():
            data[date][key] = data[date][key] + thisrow[key]
    return all_data

