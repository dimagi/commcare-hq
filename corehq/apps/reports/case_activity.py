from datetime import datetime, timedelta
from collections import defaultdict, namedtuple
import json
from corehq.apps.users.models import CouchUser
from corehq.apps.users.util import user_id_to_username
from dimagi.utils.couch.database import get_db
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.web import json_request, json_response

class CaseActivity(object):
    def __init__(self, domain, chws, case_type, landmarks, now):
        self.domain = domain
        self.chws = chws
        self.case_type = case_type
        self.landmarks = landmarks
        self.now = now

    def get_number_cases_updated(self, chw, landmark=None):
        start_time_json = json_format_datetime(self.now - landmark) if landmark else ""
        key = [self.domain, self.case_type or {}, chw]
        r = get_db().view('case/by_last_date',
            startkey=key + [start_time_json],
            endkey=key + [json_format_datetime(self.now)],
            group=True,
            group_level=0
        ).one()
        return r['value']['count'] if r else 0

    def get_data(self):
        data = defaultdict(list)
        for chw in self.chws:
            for landmark in self.landmarks:
                data[chw].append(self.get_number_cases_updated(chw, landmark))
        return data
