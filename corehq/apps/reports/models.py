from datetime import datetime
from corehq.apps import reports
from corehq.apps.reports.display import xmlns_to_name
from couchdbkit.ext.django.schema import *
from couchexport.models import SavedExportSchema
from couchexport.util import SerializableFunction
import couchforms
from dimagi.utils.mixins import UnicodeMixIn
import settings

class HQUserType:
    REGISTERED = 0
    DEMO_USER = 1
    ADMIN = 2
    UNKNOWN = 3
    human_readable = [settings.COMMCARE_USER_TERM,
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
        self.is_active = False
        self.user_data = {}

        if username == HQUserType.human_readable[HQUserType.DEMO_USER]:
            self.filter_flag = HQUserType.DEMO_USER
        elif username == HQUserType.human_readable[HQUserType.ADMIN]:
            self.filter_flag = HQUserType.ADMIN

    @property
    def get_id(self):
        return self._id
    
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

class FormExportSchema(SavedExportSchema):
    doc_type = 'SavedExportSchema'
    app_id = StringProperty()
    include_errors = BooleanProperty(default=True)

    @classmethod
    def wrap(cls, data):
        self = super(FormExportSchema, cls).wrap(data)
        if self.filter_function == 'couchforms.filters.instances':
            # grandfather in old custom exports
            self.include_errors = False
            self.filter_function = None
        return self

    @property
    def filter(self):
        f = SerializableFunction()

        if self.app_id is not None:
            f.add(reports.util.app_export_filter, app_id=self.app_id)
        if not self.include_errors:
            f.add(couchforms.filters.instances)
        return f

    @property
    def domain(self):
        return self.index[0]

    @property
    def xmlns(self):
        return self.index[1]

    @property
    def formname(self):
        return xmlns_to_name(self.domain, self.xmlns, app_id=self.app_id)