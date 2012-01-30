from collections import defaultdict
from dimagi.utils.couch.database import get_db

def get_data(domain, individual=None):
    data = defaultdict(lambda: 0)
    startkey = [domain, individual] if individual else [domain]
    endkey = [domain, individual, {}] if individual else [domain, {}]
    view = get_db().view("formtrends/form_time_by_user", 
                         startkey=startkey,
                         endkey=endkey,
                         group=True)
    for row in view:
        domain, _user, day, hour = row["key"]
        try:
            data["%d %02d" % (day, hour)] = data["%d %02d" % (day, hour)] + row["value"]
        except TypeError:
            continue

    return data