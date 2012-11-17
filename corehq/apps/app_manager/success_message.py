from datetime import timedelta, datetime
import re
from corehq.apps.users.models import CouchUser, CommCareUser
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
    def __init__(self, message, userID, domain=None, tz=timedelta(hours=0)):
        self.message = message
        self.userID = userID
        self.tz = tz
        if domain:
            self.domain = domain


    def render(self, quash=True):
        template = Template(self.message)
        try:
            return template.substitute(first_name=self.first_name,
                                   name=self.name,
                                   today=self.num_forms_today,
                                   week=self.num_forms_this_week,
                                   total=self.num_forms_all_time)
        except Exception as e:
            return ''

    def check_message(self):
        Template(self.message).substitute(first_name='', name='', today='', week='', total='')
        
    @property
    def couch_user(self):
        if not hasattr(self, '_couch_user'):
            self._couch_user = CommCareUser.get_by_user_id(self.userID)
        return self._couch_user

    @property
    def first_name(self):
        try:
            return self.couch_user.first_name
        except Exception:
            return "(?)"

    @property
    def name(self):
        try:
            return "%s %s" % (self.couch_user.first_name, self.couch_user.last_name)
        except Exception:
            return "(?)"


    def get_num_forms_since(self, time):
        if not hasattr(self, 'domain'):
            self.domain = self.couch_user.domain if self.couch_user else None

        from corehq.apps.reports.util import make_form_couch_key
        key = make_form_couch_key(self.domain, user_id=self.userID)
        r = get_db().view('reports_forms/all_forms',
            startkey=key+[json_format_datetime(time)],
            endkey=key+[{}],
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
