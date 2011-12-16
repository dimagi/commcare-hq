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
