from collections import defaultdict
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan

def get_data(domain, user=None, datespan=None):
    
    if datespan is None:
        datespan = DateSpan.since(days=300, format= "%Y-%m-%dT%H:%M:%S")
    
    data = defaultdict(lambda: 0)
    startkey = ["u", domain, user, datespan.startdate_param] if user \
                else ["d", domain, datespan.startdate_param]
    endkey = ["u", domain, user, datespan.enddate_param] if user \
                else ["d", domain, datespan.enddate_param]
    view = get_db().view("formtrends/form_duration_by_user", 
                         startkey=startkey,
                         endkey=endkey,
                         group=True,
                         reduce=True)
    for row in view:
        _dom, _user, date = row["key"]
        if not date in data:
            data[date] = defaultdict(lambda: 0)
        thisrow = row["value"]
        for key, val in thisrow.items():
            data[date][key] = data[date][key] + thisrow[key]
    return data