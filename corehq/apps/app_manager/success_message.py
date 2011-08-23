from datetime import timedelta, datetime
import re
from corehq.apps.users.models import CouchUser, CommCareAccount
from dimagi.utils.couch.database import get_db
from dimagi.utils.parsing import json_format_datetime
from string import Template

class SuccessMessage(object):
    """
    A helper for rendering the success message templates.

    #>>> SuccessMessage("Thanks $first_name! You have submitted $today forms today and $week forms since Monday.", userID).render()
    #u'Thanks Danny! You have submitted 2 forms today and 10 forms since Monday.'
    
    Valid strings are username, first_name, name, today, week, total
    """
    def __init__(self, message, userID, tz=timedelta(hours=0)):
        self.message = message
        self.userID = userID
        self.tz = tz


    def render(self):
        template = Template(self.message)
        return template.substitute(first_name=self.first_name,
                                   name=self.name,
                                   today=self.num_forms_today,
                                   week=self.num_forms_this_week,
                                   total=self.num_forms_all_time)
        
    @property
    def couch_user(self):
        if not hasattr(self, '_couch_user'):
            self._couch_user = CouchUser.view('users/by_login', key=self.userID, include_docs=True).one()
        return self._couch_user

    @property
    def first_name(self):
        return self.couch_user.first_name

    @property
    def name(self):
        return "%s %s" % (self.couch_user.first_name, self.couch_user.last_name)


    def get_num_forms_since(self, time):
        if not hasattr(self, 'domain'):
            self.domain = CommCareAccount.get_by_userID(self.userID).domain
        r = get_db().view('reports/submit_history',
            startkey=[self.domain, self.userID, json_format_datetime(time)],
            endkey=[self.domain, self.userID, {}],
            group=False
        ).one()
        return r['value'] if r else 0

    @property
    def num_forms_this_week(self):
        now = datetime.utcnow() + self.tz
        monday = now - timedelta(days=now.weekday())
        then = datetime(monday.year, monday.month, monday.day) - self.tz
        return self.get_num_forms_since(then)

    @property
    def num_forms_today(self):
        now = datetime.utcnow() + self.tz
        then = datetime(now.year, now.month, now.day) - self.tz
        return self.get_num_forms_since(then)
    
    @property
    def num_forms_all_time(self):
        return self.get_num_forms_since(datetime(1970, 1, 1))
