from collections import defaultdict
from dimagi.utils.couch.database import get_db
from random import randint
from couchdbkit.resource import ResourceNotFound
import logging

def get_data(clinic, user=None):
    
    data = defaultdict(lambda: 0)
    startkey = [clinic, user] if user else [clinic]
    endkey = [clinic, user, {}] if user else [clinic, {}]
    view = get_db().view("reports/form_duration_by_user", 
                         startkey=startkey,
                         endkey=endkey,
                         group=True,
                         reduce=True)
    for row in view:
        _clinic, _user, date = row["key"]
        if not date in data:
            data[date] = defaultdict(lambda: 0)
        thisrow = row["value"]
        for key,val in thisrow.items():
            data[date][key] = data[date][key] + thisrow[key]
    return data