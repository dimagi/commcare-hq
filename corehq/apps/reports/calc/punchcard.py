from collections import defaultdict
from dimagi.utils.couch.database import get_db
from random import randint
from couchdbkit.resource import ResourceNotFound
import logging


def get_users(domain):
    view = get_db().view("reports/form_time_by_user", 
                         startkey=[clinic],
                         endkey=[clinic,{}],
                         group=True,
                         group_level=2,
                         reduce=True)
    res = []
    for row in view:
        try:
            user_obj = get_db().get(row["key"][1])
            user_obj["get_id"] = user_obj["_id"] # hack this on, otherwise django templates get mad
            res.append((user_obj, row["value"]))
        except ResourceNotFound, e:
            logging.error("No user with id (%s) found.  What the dilly?" % row["key"][1])
    return res

    
def get_data(domain, individual=None):
    data = defaultdict(lambda: 0)
    startkey = [domain, individual] if individual else [domain]
    endkey = [domain, individual, {}] if individual else [domain, {}]
    view = get_db().view("reports/form_time_by_user", 
                         startkey=startkey,
                         endkey=endkey,
                         group=True)
    print view.all()
    for row in view:
        domain, _user, day, hour = row["key"]
        data["%d %02d" % (day, hour)] = data["%d %02d" % (day, hour)] + row["value"]
    return data