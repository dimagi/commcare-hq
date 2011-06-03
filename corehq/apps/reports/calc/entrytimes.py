from collections import defaultdict
from dimagi.utils.couch.database import get_db

def get_data(domain, user=None):
    
    data = defaultdict(lambda: 0)
    startkey = [domain, user] if user else [domain]
    endkey = [domain, user, {}] if user else [domain, {}]
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