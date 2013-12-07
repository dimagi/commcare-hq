from datetime import datetime, timedelta
import logging
from django.http import Http404
from django.utils import html
from django.utils.safestring import mark_safe
import pytz
from corehq import Domain
from corehq.apps import reports
from corehq.apps.app_manager.models import get_app
from corehq.apps.app_manager.util import ParentCasePropertyBuilder
from corehq.apps.reports.display import xmlns_to_name
from couchdbkit.ext.django.schema import *
from corehq.apps.reports.exportfilters import form_matches_users
from corehq.apps.users.models import WebUser, CommCareUser, CouchUser
from couchexport.models import SavedExportSchema, GroupExportConfiguration
from couchexport.transforms import couch_to_excel_datetime, identity
from couchexport.util import SerializableFunction
import couchforms
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
from django.core.validators import validate_email
from corehq.apps.reports.dispatcher import (ProjectReportDispatcher,
    CustomProjectReportDispatcher)
from corehq.apps.adm.dispatcher import ADMSectionDispatcher
import json
import calendar
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from dimagi.utils.logging import notify_exception


class HQUserType(object):
    REGISTERED = 0
    DEMO_USER = 1
    ADMIN = 2
    UNKNOWN = 3
    human_readable = [settings.COMMCARE_USER_TERM,
                      ugettext_noop("demo_user"),
                      ugettext_noop("admin"),
                      ugettext_noop("Unknown Users")]
    toggle_defaults = [True, False, False, False]

    @classmethod
    def use_defaults(cls, show_all=False):
        defaults = cls.toggle_defaults
        if show_all:
            defaults = [True]*4
        return [HQUserToggle(i, defaults[i]) for i in range(len(cls.human_readable))]

    @classmethod
    def all_but_users(cls):
        no_users = [False, True, True, True]
        return [HQUserToggle(i, no_users[i]) for i in range(len(cls.human_readable))]

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

    def __repr__(self):
        return "%(klass)s[%(type)s:%(show)s:%(name)s]" % dict(
            klass = self.__class__.__name__,
            type=self.type,
            name=self.name,
            show=self.show
        )


class HQUserToggle(HQToggle):
    
    def __init__(self, type, show):
        name = _(HQUserType.human_readable[type])
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

    def delete(self, *args, **kwargs):
        notifications = self.view('reportconfig/notifications_by_config',
            reduce=False, include_docs=True, key=self._id).all()

        for n in notifications:
            n.config_ids.remove(self._id)
            if n.config_ids:
                n.save()
            else:
                n.delete()

        return super(ReportConfig, self).delete(*args, **kwargs)

    @classmethod
    def by_domain_and_owner(cls, domain, owner_id, report_slug=None,
                            stale=True, **kwargs):
        if stale:
            #kwargs['stale'] = settings.COUCH_STALE_QUERY
            pass

        if report_slug is not None:
            key = ["name slug", domain, owner_id, report_slug]
        else:
            key = ["name", domain, owner_id]

        db = cls.get_db()
        result = cache_core.cached_view(db, "reportconfig/configs_by_domain", reduce=False,
                                     include_docs=True, startkey=key, endkey=key + [{}], wrapper=cls.wrap, **kwargs)
        return result

    @classmethod
    def default(self):
        return {
            'name': '',
            'description': '',
            #'date_range': 'last7',
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
        if self._id != 'dummy':
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
        try:
            from django.core.urlresolvers import reverse
            
            return reverse(self._dispatcher.name(), kwargs=self.view_kwargs) \
                    + '?' + self.query_string
        except Exception:
            return "#"

    @property
    @memoized
    def report(self):
        """
        Returns None if no report is found for that report slug, which happens
        when a report is no longer available.  All callers should handle this
        case.

        """
        return self._dispatcher.get_report(self.domain, self.report_slug)

    @property
    def report_name(self):
        try:
            if self.report is None:
                return _("Deleted Report")
            else:
                return _(self.report.name)
        except Exception:
            return _("Unsupported Report")

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
        elif self.start_date:
            return "Since %s" % self.start_date
        else:
            return ''

    @property
    @memoized
    def owner(self):
        try:
            return WebUser.get_by_user_id(self.owner_id)
        except CouchUser.AccountTypeError:
            return CommCareUser.get_by_user_id(self.owner_id)

    def get_report_content(self):
        """
        Get the report's HTML content as rendered by the static view format.

        """
        try:
            if self.report is None:
                return _("The report used to create this scheduled report is no"
                         " longer available on CommCare HQ.  Please delete this"
                         " scheduled report and create a new one using an available"
                         " report.")
        except Exception:
            pass

        from django.http import HttpRequest, QueryDict
        request = HttpRequest()
        request.couch_user = self.owner
        request.user = self.owner.get_django_user()
        request.domain = self.domain
        request.couch_user.current_domain = self.domain

        request.GET = QueryDict(self.query_string + '&filterSet=true')

        try:
            response = self._dispatcher.dispatch(request, render_as='email',
                **self.view_kwargs)
            return json.loads(response.content)['report']
        except Exception:
            notify_exception(None, "Error generating report")
            return _("An error occurred while generating this report.")


class UnsupportedScheduledReportError(Exception):
    pass


class ReportNotification(Document):
    domain = StringProperty()
    owner_id = StringProperty()

    recipient_emails = StringListProperty()
    config_ids = StringListProperty()
    send_to_owner = BooleanProperty()

    hour = IntegerProperty(default=8)
    day = IntegerProperty(default=1)
    interval = StringProperty(choices=["daily", "weekly", "monthly"])


    @property
    def is_editable(self):
        try:
            self.report_slug
            return False
        except AttributeError:
            return True
        
    @classmethod
    def by_domain_and_owner(cls, domain, owner_id, stale=True, **kwargs):
        if stale:
            kwargs['stale'] = settings.COUCH_STALE_QUERY

        key = [domain, owner_id]

        db = cls.get_db()
        result = cache_core.cached_view(db, "reportconfig/user_notifications", reduce=False,
                                     include_docs=True, startkey=key, endkey=key + [{}], wrapper=cls.wrap, **kwargs)
        return result

    @property
    def all_recipient_emails(self):
        # handle old documents
        if not self.owner_id:
            return [self.owner.get_email()]

        emails = []
        if self.send_to_owner:
            if self.owner.is_web_user():
                emails.append(self.owner.username)
            else:
                email = self.owner.get_email()
                try:
                    validate_email(email)
                    emails.append(email)
                except Exception:
                    pass
        emails.extend(self.recipient_emails)
        return emails

    @property
    @memoized
    def owner(self):
        id = self.owner_id
        try:
            return WebUser.get_by_user_id(id)
        except CouchUser.AccountTypeError:
            return CommCareUser.get_by_user_id(id)

    @property
    @memoized
    def configs(self):
        """
        Access the notification's associated configs as a list, transparently
        returning an appropriate dummy for old notifications which have
        `report_slug` instead of `config_ids`.

        """
        if self.config_ids:
            configs = ReportConfig.view('_all_docs', keys=self.config_ids,
                include_docs=True).all()
            configs = [c for c in configs if not hasattr(c, 'deleted')]
        elif self.report_slug == 'admin_domains':
            raise UnsupportedScheduledReportError("admin_domains is no longer "
                "supported as a schedulable report for the time being")
        else:
            # create a new ReportConfig object, useful for its methods and
            # calculated properties, but don't save it
            class ReadonlyReportConfig(ReportConfig):
                def save(self, *args, **kwargs):
                    pass

            config = ReadonlyReportConfig()
            object.__setattr__(config, '_id', 'dummy')
            config.report_type = ProjectReportDispatcher.prefix
            config.report_slug = self.report_slug
            config.domain = self.domain
            config.owner_id = self.owner_id
            configs = [config]

        return configs

    @property
    def day_name(self):
        if self.interval == 'weekly':
            return calendar.day_name[self.day]
        return {
            "daily": _("Every day"),
            "monthly": _("Day %s of every month" % self.day),
        }[self.interval]

    @classmethod
    def day_choices(cls):
        """Tuples for day of week number and human-readable day of week"""
        return tuple([(val, calendar.day_name[val]) for val in range(7)])

    @classmethod
    def hour_choices(cls):
        """Tuples for hour number and human-readable hour"""
        return tuple([(val, "%s:00" % val) for val in range(24)])

    def send(self):
        from dimagi.utils.django.email import send_HTML_email
        from corehq.apps.reports.views import get_scheduled_report_response

        # Scenario: user has been removed from the domain that they
        # have scheduled reports for.  Delete this scheduled report
        if not self.owner.is_member_of(self.domain):
            self.delete()
            return

        if self.all_recipient_emails:
            title = "Scheduled report from CommCare HQ"
            body = get_scheduled_report_response(self.owner, self.domain, self._id).content
            for email in self.all_recipient_emails:
                send_HTML_email(title, email, body, email_from=settings.DEFAULT_FROM_EMAIL)


class AppNotFound(Exception):
    pass


class HQExportSchema(SavedExportSchema):
    doc_type = 'SavedExportSchema'
    domain = StringProperty()
    transform_dates = BooleanProperty(default=True)

    @property
    def global_transform_function(self):
        if self.transform_dates:
            return couch_to_excel_datetime
        else:
            return identity

    @classmethod
    def wrap(cls, data):
        if 'transform_dates' not in data:
            data['transform_dates'] = False
        self = super(HQExportSchema, cls).wrap(data)
        if not self.domain:
            self.domain = self.index[0]
        return self

class FormExportSchema(HQExportSchema):
    doc_type = 'SavedExportSchema'
    app_id = StringProperty()
    include_errors = BooleanProperty(default=False)

    @property
    @memoized
    def app(self):
        if self.app_id:
            try:
                return get_app(self.domain, self.app_id, latest=True)
            except Http404:
                logging.error('App %s in domain %s not found for export %s' % (
                    self.app_id,
                    self.domain,
                    self.get_id
                ))
                raise AppNotFound()
        else:
            return None

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
        user_ids = set(CouchUser.ids_by_domain(self.domain))
        user_ids.update(CouchUser.ids_by_domain(self.domain, is_active=False))
        f = SerializableFunction(form_matches_users, users=user_ids)
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

    @property
    @memoized
    def question_order(self):
        try:
            if not self.app:
                return []
        except AppNotFound:
            if settings.DEBUG:
                return []
            raise
        else:
            questions = self.app.get_questions(self.xmlns)

        order = []
        for question in questions:
            index_parts = question['value'].split('/')
            assert index_parts[0] == ''
            index_parts[1] = 'form'
            index = '.'.join(index_parts[1:])
            order.append(index)

        return order

    def get_default_order(self):
        return {'#': self.question_order}


class FormDeidExportSchema(FormExportSchema):

    @property
    def transform(self):
        return SerializableFunction()

    @classmethod
    def get_case(cls, doc, case_id):
        pass

class CaseExportSchema(HQExportSchema):
    doc_type = 'SavedExportSchema'

    @property
    def domain(self):
        return self.index[0]

    @property
    def domain_obj(self):
        return Domain.get_by_name(self.domain)

    @property
    def case_type(self):
        return self.index[1]

    @property
    def applications(self):
        return self.domain_obj.full_applications(include_builds=False)

    @property
    def case_properties(self):
        props = set([])
        for app in self.applications:
            builder = ParentCasePropertyBuilder(app, ("name",))
            props |= set(builder.get_properties(self.case_type))
        return props

class HQGroupExportConfiguration(GroupExportConfiguration):
    """
    HQ's version of a group export, tagged with a domain
    """
    domain = StringProperty()

    def get_custom_exports(self):

        def _rewrap(export):
            # custom wrap if relevant
            try:
                return {
                    'form': FormExportSchema,
                }[export.type].wrap(export._doc)
            except KeyError:
                return export

        for custom in list(self.custom_export_ids):
            custom_export = self._get_custom(custom)
            if custom_export:
                yield _rewrap(custom_export)

    @classmethod
    def by_domain(cls, domain):
        return cache_core.cached_view(cls.get_db(), "groupexport/by_domain", key=domain, reduce=False, include_docs=True, wrapper=cls.wrap)

    @classmethod
    def get_for_domain(cls, domain):
        """
        For when we only expect there to be one of these per domain,
        which right now is always.
        """
        groups = cls.by_domain(domain)
        if groups:
            if len(groups) > 1:
                logging.error("Domain %s has more than one group export config! This is weird." % domain)
            return groups[0]
        return HQGroupExportConfiguration(domain=domain)

    @classmethod
    def add_custom_export(cls, domain, export_id):
        group = cls.get_for_domain(domain)
        if export_id not in group.custom_export_ids:
            group.custom_export_ids.append(export_id)
            group.save()
        return group

    @classmethod
    def remove_custom_export(cls, domain, export_id):
        group = cls.get_for_domain(domain)
        updated = False
        while export_id in group.custom_export_ids:
            group.custom_export_ids.remove(export_id)
            updated = True
        if updated:
            group.save()
        return group


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
