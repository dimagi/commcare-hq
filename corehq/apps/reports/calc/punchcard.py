from collections import defaultdict
from dimagi.utils.couch.database import get_db
from random import randint
from couchdbkit.resource import ResourceNotFound
import logging


def get_data(domain, individual=None):
    data = defaultdict(lambda: 0)
    startkey = [domain, individual] if individual else [domain]
    endkey = [domain, individual, {}] if individual else [domain, {}]
    view = get_db().view("punchcard/form_time_by_user", 
                         startkey=startkey,
                         endkey=endkey,
                         group=True)
    for row in view:
        domain, _user, day, hour = row["key"]
        data["%d %02d" % (day, hour)] = data["%d %02d" % (day, hour)] + row["value"]
    return data