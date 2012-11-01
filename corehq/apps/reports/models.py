from datetime import datetime, timedelta
from django.utils import html
from django.utils.safestring import mark_safe
import pytz
from corehq.apps import reports
from corehq.apps.reports.display import xmlns_to_name
from couchdbkit.ext.django.schema import *
from corehq.apps.users.models import CouchUser, CommCareUser
from couchexport.models import SavedExportSchema, GroupExportConfiguration
from couchexport.util import SerializableFunction
import couchforms
from dimagi.utils.couch.database import get_db
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.decorators.memoized import memoized
import settings
from corehq.apps.reports.dispatcher import (ProjectReportDispatcher,
    CustomProjectReportDispatcher)
from corehq.apps.adm.dispatcher import ADMSectionDispatcher
import json

class HQUserType(object):
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
    def use_defaults(cls, show_all=False):
        defaults = cls.toggle_defaults
        if show_all:
            defaults = [True]*4
        return [HQUserToggle(i, defaults[i]) for i in range(len(cls.human_readable))]

    @classmethod
    def use_filter(cls, ufilter):
        return [HQUserToggle(i, unicode(i) in ufilter) for i in range(len(cls.human_readable))]

class HQToggle(object):
    type = None
    show = False
    name = None
    
    def __init__(self, type, show, name):
        self.type = type
        self.name = name
        self.show = show

    def __str__(self):
        return "%(klass)s[%(type)s:%(show)s:%(name)s]" % dict(
            klass = self.__class__.__name__,
            type=self.type,
            name=self.name,
            show=self.show
        )

class HQUserToggle(HQToggle):
    
    def __init__(self, type, show):
        name = HQUserType.human_readable[type]
        super(HQUserToggle, self).__init__(type, show, name)


class TempCommCareUser(CommCareUser):
    filter_flag = IntegerProperty()

    def __init__(self, domain, username, uuid):
        if username == HQUserType.human_readable[HQUserType.DEMO_USER]:
            filter_flag = HQUserType.DEMO_USER
        elif username == HQUserType.human_readable[HQUserType.ADMIN]:
            filter_flag = HQUserType.ADMIN
        else:
            filter_flag = HQUserType.UNKNOWN
        super(TempCommCareUser, self).__init__(
            domain=domain,
            username=username,
            _id=uuid,
            date_joined=datetime.utcnow(),
            is_active=False,
            user_data={},
            first_name='',
            last_name='',
            filter_flag=filter_flag
        )

    def save(self, **params):
        raise NotImplementedError

    @property
    def userID(self):
        return self._id

    @property
    def username_in_report(self):
        if self.filter_flag == HQUserType.UNKNOWN:
            final = mark_safe('%s <strong>[unregistered]</strong>' % html.escape(self.username))
        elif self.filter_flag == HQUserType.DEMO_USER:
            final = mark_safe('<strong>%s</strong>' % html.escape(self.username))
        else:
            final = mark_safe('<strong>%s</strong> (%s)' % tuple(map(html.escape, [self.username, self.user_id])))
        return final

    @property
    def raw_username(self):
        return self.username

    class Meta:
        app_label = 'reports'



DATE_RANGE_CHOICES = ['last7', 'last30', 'lastn', 'since', 'range']

class ReportConfig(Document):
    _extra_json_properties = ['url', 'report_name', 'date_description']

    domain = StringProperty()

    # the prefix of the report dispatcher class for this report, used to
    # get route name for url reversing, and report names
    report_type = StringProperty()
    report_slug = StringProperty()
    subreport_slug = StringProperty(default=None)

    name = StringProperty()
    description = StringProperty()
    owner_id = StringProperty()

    filters = DictProperty()

    date_range = StringProperty(choices=DATE_RANGE_CHOICES)
    days = IntegerProperty(default=None)
    start_date = DateProperty(default=None)
    end_date = DateProperty(default=None)

    @classmethod
    def by_domain_and_owner(cls, domain, owner_id, report_slug=None, include_docs=True):
        key = [domain, owner_id]
        if report_slug:
            key.append(report_slug)

        return cls.view('reportconfig/configs_by_domain',
            reduce=False,
            include_docs=include_docs,
            startkey=key,
            endkey=key + [{}])
   
    @classmethod
    def default(self):
        return {
            'name': '',
            'description': '',
            'date_range': 'last7',
            'days': None,
            'start_date': None,
            'end_date': None,
            'filters': {}
        }

    def to_complete_json(self):
        json = super(ReportConfig, self).to_json()

        for key in self._extra_json_properties:
            json[key] = getattr(self, key)
        
        return json

    @property
    @memoized
    def _dispatcher(self):

        dispatchers = [ProjectReportDispatcher,
                       CustomProjectReportDispatcher,
                       ADMSectionDispatcher]

        for dispatcher in dispatchers:
            if dispatcher.prefix == self.report_type:
                return dispatcher()

        raise Exception("Unknown dispatcher: %s" % self.report_type)

    def get_date_range(self):
        """Duplicated in reports.config.js"""
        
        date_range = self.date_range

        # allow old report email notifications to represent themselves as a
        # report config by leaving the default date range up to the report
        # dispatcher
        if not date_range:
            return {}

        import datetime
        today = datetime.date.today()

        if date_range == 'since':
            start_date = self.start_date
            end_date = today
        elif date_range == 'range':
            start_date = self.start_date
            end_date = self.end_date
        else:
            end_date = today

            if date_range == 'last7':
                days = 7
            elif date_range == 'last30':
                days = 30
            elif date_range == 'lastn':
                days = self.days
            else:
                raise Exception("Invalid date range")

            start_date = today - datetime.timedelta(days=days)

        return {'startdate': start_date.isoformat(),
                'enddate': end_date.isoformat()}

    @property
    @memoized
    def query_string(self):
        from urllib import urlencode

        params = self.filters.copy()
        params['config_id'] = self._id
        params.update(self.get_date_range())

        return urlencode(params, True)

    @property
    @memoized
    def view_kwargs(self):
        kwargs = {'domain': self.domain,
                  'report_slug': self.report_slug}

        if self.subreport_slug:
            kwargs['subreport_slug'] = self.subreport_slug

        return kwargs

    @property
    @memoized
    def url(self):
        from django.core.urlresolvers import reverse
        
        return reverse(self._dispatcher.name(), kwargs=self.view_kwargs) \
                + '?' + self.query_string

    @property
    @memoized
    def report(self):
        return self._dispatcher.get_report(self.domain, self.report_slug)

    @property
    def report_name(self):
        return self.report.name

    @property
    def full_name(self):
        if self.name:
            return "%s (%s)" % (self.name, self.report_name)
        else:
            return self.report_name

    @property
    def date_description(self):
        if self.days and not self.start_date:
            day = 'day' if self.days == 1 else 'days'
            return "Last %d %s" % (self.days, day)
        elif self.end_date:
            return "From %s to %s" % (self.start_date, self.end_date)
        else:
            return "Since %s" % self.start_date

    @property
    @memoized
    def owner(self):
        return CouchUser.get(self.owner_id)

    def get_report_content(self, request_domain, request_user):
        """
        Get the report's HTML content as rendered by the static view format.
        This method doesn't really have a natural place in this class, but it's
        better than duplicating the code in tasks and emailtest.

        """
        from django.http import HttpRequest, QueryDict

        request = HttpRequest()
        request.couch_user = request_user
        request.user = request_user.get_django_user()
        request.domain = request_domain
        request.couch_user.current_domain = request_domain

        request.GET = QueryDict(self.query_string + '&filterSet=true')

        content = self._dispatcher.dispatch(request, render_as='static',
                                            **self.view_kwargs).content
        return json.loads(content)['report']


class ReportNotification(Document, UnicodeMixIn):
    user_ids = StringListProperty()
    config_id = StringProperty()  # added 10/2012

    # report_slug = StringProperty()  # removed 10/2012
    # domain = StringProperty()  # removed 10/2012

    @property
    @memoized
    def config(self):
        """
        Access the notification's config object, transparently returning an
        appropriate dummy object for old notifications which have `report_slug`
        instead of `config_id`.

        """
        if self.config_id:
            config = ReportConfig.get(self.config_id)
        else:
            # create a new ReportConfig object, useful for its methods and
            # calculated properties, but don't save it
            config = ReportConfig()
            config.save = lambda self, *args, **kwargs: None
            object.__setattr__(config, '_id', 'dummy')
            config.report_type = 'project_report'
            config.report_slug = self.report_slug
            config.domain = self.domain
            config.owner_id = self.user_ids[0]

        return config

    def remove_user(self, user_id):
        self.user_ids.remove(user_id)
        if self.user_ids:
            self.save()
        else:
            self.delete()

    @classmethod
    def days(cls):
        """List of tuples for day of week number and human-readable day of week"""
        import calendar
        return [(val, calendar.day_name[val]) for val in range(7)]

    @classmethod
    def hours(cls):
        """List of tuples for hour number and human-readable hour"""
        return [(val, "%s:00" % val) for val in range(24)]




    
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

class FormDeidExportSchema(FormExportSchema):

    @property
    def transform(self):
        return SerializableFunction()

    @classmethod
    def get_case(cls, doc, case_id):
        pass
    
class HQGroupExportConfiguration(GroupExportConfiguration):
    """
    HQ's version of a group export, tagged with a domain
    """
    domain = StringProperty()
    
    @classmethod
    def by_domain(cls, domain):
        return cls.view("groupexport/by_domain", key=domain, 
                        reduce=False, include_docs=True).all()

class CaseActivityReportCache(Document):
    domain = StringProperty()
    timezone = StringProperty()
    last_updated = DateTimeProperty()
    active_cases = DictProperty()
    closed_cases = DictProperty()
    inactive_cases = DictProperty()
    landmark_data = DictProperty()

    _couch_view = "reports/case_activity"
    _default_case_key = "__DEFAULT__"

    _case_list = None
    @property
    def case_list(self):
        if not self._case_list:
            key = ["type", self.domain]
            data = get_db().view(self._couch_view,
                group=True,
                group_level=3,
                startkey=key,
                endkey=key+[{}]
            ).all()
            self._case_list = [None] + [item.get('key',[])[-1] for item in data]
        return self._case_list

    _now = None
    @property
    def now(self):
        if not self._now:
            self._now = datetime.now(tz=pytz.timezone(str(self.timezone)))
            self._now = self._now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return self._now

    _milestone = None
    @property
    def milestone(self):
        if not self._milestone:
            self._milestone = self._now - timedelta(days=121)
        return self._milestone

    def _get_user_id_counts(self, data):
        result = dict()
        for item in data:
            count = item.get('value', 0)
            user_id = item.get('key',[])[-1]
            if user_id:
                if not user_id in result:
                    result[user_id] = count
                else:
                    result[user_id] += count
        return result

    def _generate_landmark(self, landmark, case_type=None):
        """
            Generates a dict with counts per owner_id of the # cases modified or closed in
            the last <landmark> days.
        """
        prefix = "" if case_type is None else "type"
        key = [prefix, self.domain]
        if case_type is not None:
            key.append(case_type)


        past = self.now - timedelta(days=landmark+1)
        data = get_db().view(self._couch_view,
            group=True,
            startkey=key+[past.isoformat()],
            endkey=key+[self.now.isoformat(), {}]
        ).all()
        return self._get_user_id_counts(data)

    def _generate_status_key(self, case_type, status="open"):
        prefix = ["status"]
        key = [self.domain, status]
        if case_type is not None:
            prefix.append("type")
            key.append(case_type)
        return [" ".join(prefix)] + key

    def _generate_case_status(self, milestone=120, case_type=None, active=True, status="open"):
        """
            inactive: Generates a dict with counts per owner_id of the number of cases that are open,
            but haven't been modified in the last 120 days.
            active: Generates a dict with counts per owner_id of the number of cases that are open
            and have been modified in the last 120 days.
        """
        key = self._generate_status_key(case_type, status)
        milestone = self.now - timedelta(days=milestone+1) + (timedelta(microseconds=1) if active else timedelta(seconds=0))
        data = get_db().view(self._couch_view,
            group=True,
            startkey=key+([milestone.isoformat()] if active else []),
            endkey=key+([self.now.isoformat()] if active else [milestone.isoformat()])
        ).all()
        return self._get_user_id_counts(data)

    def case_key(self, case_type):
        return case_type if case_type is not None else self._default_case_key

    def day_key(self, days):
        return "%s_days" % days

    def update_landmarks(self, landmarks=None):
        landmarks = landmarks if landmarks else [30, 60, 90]
        for case_type in self.case_list:
            case_key = self.case_key(case_type)
            if not case_key in self.landmark_data:
                self.landmark_data[case_key] = dict()
            for landmark in landmarks:
                self.landmark_data[case_key][self.day_key(landmark)] = self._generate_landmark(landmark, case_type)

    def update_status(self, milestone=120):
        for case_type in self.case_list:
            case_key = self.case_key(case_type)
            if case_key not in self.active_cases:
                self.active_cases[case_key] = dict()
            if case_key not in self.inactive_cases:
                self.inactive_cases[case_key] = dict()
            if case_key not in self.closed_cases:
                self.closed_cases[case_key] = dict()

            self.active_cases[case_key][self.day_key(milestone)] = self._generate_case_status(milestone, case_type)
            self.closed_cases[case_key][self.day_key(milestone)] = self._generate_case_status(milestone,
                                                                                                case_type, status="closed")
            self.inactive_cases[case_key][self.day_key(milestone)] = self._generate_case_status(milestone,
                                                                                                case_type, active=False)

    @classmethod
    def get_by_domain(cls, domain, include_docs=True):
        return cls.view('reports/case_activity_cache',
            reduce=False,
            include_docs=include_docs,
            key=domain
        )

    @classmethod
    def build_report(cls, domain):
        report = cls.get_by_domain(domain.name).first()
        if not report:
            report = cls(domain=str(domain.name))
        report.timezone = domain.default_timezone
        report.update_landmarks()
        report.update_status()
        report.last_updated = datetime.utcnow()
        report.save()
        return report
