from datetime import datetime
from couchdbkit.ext.django.schema import *
from dimagi.utils.mixins import UnicodeMixIn

class HQUserType:
    REGISTERED = 0
    DEMO_USER = 1
    ADMIN = 2
    UNKNOWN = 3
    human_readable = ["CommCare Users",
                      "demo_user",
                      "admin",
                      "Unknown Users"]
    toggle_defaults = [True, False, False, False]

    @classmethod
    def use_defaults(cls):
        return [HQUserToggle(i, cls.toggle_defaults[i]) for i in range(len(cls.human_readable))]

    @classmethod
    def use_filter(cls, ufilter):
        return [HQUserToggle(i, unicode(i) in ufilter) for i in range(len(cls.human_readable))]

class HQUserToggle:
    type = None
    show = False
    name = None

    def __init__(self, type, show):
        self.type = type
        self.name = HQUserType.human_readable[self.type]
        self.show = show

class TempCommCareUser:
    filter_flag = HQUserType.UNKNOWN

    def __init__(self, domain, username, uuid):
        self.domain = domain
        self.username = username
        self._id = uuid
        self.date_joined = datetime.utcnow()

        if username == HQUserType.human_readable[HQUserType.DEMO_USER]:
            self.filter_flag = HQUserType.DEMO_USER
        elif username == HQUserType.human_readable[HQUserType.ADMIN]:
            self.filter_flag = HQUserType.ADMIN

    @property
    def user_id(self):
        return self._id

    @property
    def userID(self):
        return self._id

    @property
    def username_in_report(self):
        if self.filter_flag == HQUserType.UNKNOWN:
            final = '%s <strong>[unregistered]</strong>' % self.username
        elif self.filter_flag == HQUserType.DEMO_USER:
            final = '<strong>%s</strong>' % self.username
        else:
            final = '<strong>%s</strong> (%s)' % (self.username, self.user_id)
        return final

    @property
    def raw_username(self):
        return self.username

class ReportNotification(Document, UnicodeMixIn):
    domain = StringProperty()
    user_ids = StringListProperty()
    report_slug = StringProperty()
    
    def __unicode__(self):
        return "Notify: %s user(s): %s, report: %s" % \
                (self.doc_type, ",".join(self.user_ids), self.report_slug)
    
class DailyReportNotification(ReportNotification):
    hours = IntegerProperty()
    
    
class WeeklyReportNotification(ReportNotification):
    hours = IntegerProperty()
    day_of_week = IntegerProperty()
