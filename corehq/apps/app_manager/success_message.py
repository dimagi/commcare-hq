from datetime import timedelta, datetime
import re
from corehq.apps.users.models import CouchUser, CommCareAccount
from dimagi.utils.couch.database import get_db
from dimagi.utils.parsing import json_format_datetime

class SuccessMessage(object):
    """
    A helper for rendering the success message templates.

    #>>> SuccessMessage("Thanks {first_name}! You have submitted {num_forms_today} forms today and {num_forms_this_week} forms since Monday.", userID).render()
    #u'Thanks Danny! You have submitted 2 forms today and 10 forms since Monday.'
    """
    def __init__(self, message, userID, tz=timedelta(hours=0)):
        self.message = message
        self.userID = userID
        self.tz = tz


    def render(self):
        message = self.message
        for var in ('first_name', 'name', 'num_forms_this_week', 'num_forms_today'):
            if re.search("{%s}" % var, message):
                message = re.sub("{%s}" % var, unicode(getattr(self, var)), message)
        return message

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
