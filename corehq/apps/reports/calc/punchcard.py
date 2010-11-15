from collections import defaultdict
from dimagi.utils.couch.database import get_db
from random import randint
from couchdbkit.resource import ResourceNotFound
import logging

def get_clinics():
    view = get_db().view("reports/form_time_by_user", 
                         group=True,
                         group_level=1,
                         reduce=True)
    return dict([(row["key"][0], row["value"]) for row in view])

def get_users(clinic):
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
        
    
def get_data(clinic, user=None):
    
    data = defaultdict(lambda: 0)
    startkey = [clinic, user] if user else [clinic]
    endkey = [clinic, user, {}] if user else [clinic, {}]
    view = get_db().view("reports/form_time_by_user", 
                         startkey=startkey,
                         endkey=endkey,
                         group=True,
                         reduce=True)
    for row in view:
        _clinic, _user, day, hour = row["key"]
        data["%d %02d" % (day, hour)] = data["%d %02d" % (day, hour)] + row["value"]
    return data