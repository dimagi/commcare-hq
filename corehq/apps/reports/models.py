import calendar
from collections import defaultdict, namedtuple
from datetime import datetime
import functools
import json
import logging
from urllib import urlencode

from django.http import Http404
from django.utils import html
from django.utils.safestring import mark_safe
from django.conf import settings
from django.core.validators import validate_email
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from sqlalchemy.util import immutabledict

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Form, RemoteApp
from corehq.apps.app_manager.util import get_case_properties
from corehq.apps.cachehq.mixins import (
    CachedCouchDocumentMixin,
    QuickCachedDocumentMixin,
)
from corehq.apps.domain.middleware import CCHQPRBACMiddleware
from corehq.apps.domain.models import Domain
from corehq.apps.export.models import FormQuestionSchema
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.reports.daterange import get_daterange_start_end_dates, get_all_daterange_slugs
from corehq.apps.reports.dbaccessors import (
    hq_group_export_configs_by_domain,
    stale_get_exports_json,
)
from corehq.apps.reports.dispatcher import ProjectReportDispatcher, CustomProjectReportDispatcher
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.exceptions import (
    InvalidDaterangeException,
    UnsupportedSavedReportError,
    UnsupportedScheduledReportError,
)
from corehq.apps.reports.exportfilters import (
    default_case_filter,
    default_form_filter,
    form_matches_users,
    is_commconnect_form,
)
from corehq.apps.userreports.util import default_language as ucr_default_language, localize as ucr_localize
from corehq.apps.users.dbaccessors import get_user_docs_by_username
from corehq.apps.users.models import WebUser, CommCareUser, CouchUser
from corehq.util.quickcache import quickcache
from corehq.util.translation import localize
from corehq.util.view_utils import absolute_reverse

from couchexport.models import SavedExportSchema, GroupExportConfiguration, DefaultExportSchema, SplitColumn
from couchexport.transforms import couch_to_excel_datetime, identity
from couchexport.util import SerializableFunction
from couchforms.filters import instances
from dimagi.ext.couchdbkit import *
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception
from django_prbac.exceptions import PermissionDenied


class HQUserType(object):
    REGISTERED = 0
    DEMO_USER = 1
    ADMIN = 2
    UNKNOWN = 3
    COMMTRACK = 4
    human_readable = [settings.COMMCARE_USER_TERM,
                      ugettext_noop("demo_user"),
                      ugettext_noop("admin"),
                      ugettext_noop("Unknown Users"),
                      ugettext_noop("CommCare Supply")]
    toggle_defaults = (True, False, False, False, False)
    count = len(human_readable)
    included_defaults = (True, True, True, True, False)

    @classmethod
    def use_defaults(cls):
        return cls._get_manual_filterset(cls.included_defaults, cls.toggle_defaults)

    @classmethod
    def all_but_users(cls):
        no_users = [True] * cls.count
        no_users[cls.REGISTERED] = False
        return cls._get_manual_filterset(cls.included_defaults, no_users)

    @classmethod
    def commtrack_defaults(cls):
        # this is just a convenience method for clairty on commtrack projects
        return cls.all()

    @classmethod
    def all(cls):
        defaults = (True,) * cls.count
        return cls._get_manual_filterset(defaults, cls.toggle_defaults)

    @classmethod
    def _get_manual_filterset(cls, included, defaults):
        """
        manually construct a filter set. included and defaults should both be
        arrays of booleans mapping to values in human_readable and whether they should be
        included and defaulted, respectively.
        """
        return [HQUserToggle(i, defaults[i]) for i in range(cls.count) if included[i]]

    @classmethod
    def use_filter(cls, ufilter):
        return [HQUserToggle(i, unicode(i) in ufilter) for i in range(cls.count)]


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


ReportContent = namedtuple('ReportContent', ['text', 'attachment'])


class ReportConfig(CachedCouchDocumentMixin, Document):

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

    date_range = StringProperty(choices=get_all_daterange_slugs())
    days = IntegerProperty(default=None)
    start_date = DateProperty(default=None)
    end_date = DateProperty(default=None)
    datespan_slug = StringProperty(default=None)

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
                            stale=True, skip=None, limit=None):
        kwargs = {}
        if stale:
            kwargs['stale'] = settings.COUCH_STALE_QUERY
            pass

        if report_slug is not None:
            key = ["name slug", domain, owner_id, report_slug]
        else:
            key = ["name", domain, owner_id]

        db = cls.get_db()
        if skip is not None:
            kwargs['skip'] = skip
        if limit is not None:
            kwargs['limit'] = limit

        result = cache_core.cached_view(
            db,
            "reportconfig/configs_by_domain",
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key + [{}],
            wrapper=cls.wrap,
            **kwargs
        )
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

    def to_complete_json(self, lang=None):
        result = super(ReportConfig, self).to_json()
        result.update({
            'url': self.url,
            'report_name': self.report_name,
            'date_description': self.date_description,
            'datespan_filters': self.datespan_filter_choices(
                self.datespan_filters,
                lang or ucr_default_language()
            ),
            'has_ucr_datespan': self.has_ucr_datespan,
        })
        return result

    @property
    @memoized
    def _dispatcher(self):
        from corehq.apps.userreports.models import CUSTOM_REPORT_PREFIX
        from corehq.apps.userreports.reports.view import (
            ConfigurableReport,
            CustomConfigurableReportDispatcher,
        )

        dispatchers = [
            ProjectReportDispatcher,
            CustomProjectReportDispatcher,
        ]

        for dispatcher in dispatchers:
            if dispatcher.prefix == self.report_type:
                return dispatcher()

        if self.report_type == 'configurable':
            if self.subreport_slug.startswith(CUSTOM_REPORT_PREFIX):
                return CustomConfigurableReportDispatcher()
            else:
                return ConfigurableReport()

        if self.doc_type != 'ReportConfig-Deleted':
            self.doc_type += '-Deleted'
            self.save()
            notify_exception(
                None,
                "This saved-report (id: %s) is unknown (report_type: %s) and so we have archived it" % (
                    self._id,
                    self.report_type
                )
            )
        raise UnsupportedSavedReportError("Unknown dispatcher: %s" % self.report_type)

    def get_date_range(self):
        """Duplicated in reports.config.js"""
        date_range = self.date_range
        # allow old report email notifications to represent themselves as a
        # report config by leaving the default date range up to the report
        # dispatcher
        if not date_range:
            return {}

        try:
            start_date, end_date = get_daterange_start_end_dates(
                date_range,
                start_date=self.start_date,
                end_date=self.end_date,
                days=self.days,
            )
        except InvalidDaterangeException:
            # this is due to bad validation. see: http://manage.dimagi.com/default.asp?110906
            logging.error('saved report %s is in a bad state - date range is misconfigured' % self._id)
            return {}

        dates = {
            'startdate': start_date.isoformat(),
            'enddate': end_date.isoformat(),
        }

        if self.is_configurable_report:
            filter_slug = self.datespan_slug
            if filter_slug:
                return {
                    '%s-start' % filter_slug: start_date.isoformat(),
                    '%s-end' % filter_slug: end_date.isoformat(),
                    filter_slug: '%(startdate)s to %(enddate)s' % dates,
                }
        return dates

    @property
    @memoized
    def query_string(self):
        params = {}
        if self._id != 'dummy':
            params['config_id'] = self._id
        if not self.is_configurable_report:
            params.update(self.filters)
            params.update(self.get_date_range())

        return urlencode(params, True)

    @property
    @memoized
    def url_kwargs(self):
        kwargs = {
            'domain': self.domain,
            'report_slug': self.report_slug,
        }

        if self.subreport_slug:
            kwargs['subreport_slug'] = self.subreport_slug

        return immutabledict(kwargs)

    @property
    @memoized
    def view_kwargs(self):
        if not self.is_configurable_report:
            return self.url_kwargs.union({
                'permissions_check': self._dispatcher.permissions_check,
            })
        return self.url_kwargs

    @property
    @memoized
    def url(self):
        try:
            from corehq.apps.userreports.reports.view import ConfigurableReport

            if self.is_configurable_report:
                url_base = absolute_reverse(self.report_slug, args=[self.domain, self.subreport_slug])
            else:
                url_base = absolute_reverse(self._dispatcher.name(), kwargs=self.url_kwargs)
            return url_base + '?' + self.query_string
        except UnsupportedSavedReportError:
            return "#"
        except Exception as e:
            logging.exception(e.message)
            return "#"

    @property
    @memoized
    def report(self):
        """
        Returns None if no report is found for that report slug, which happens
        when a report is no longer available.  All callers should handle this
        case.

        """
        try:
            return self._dispatcher.get_report(
                self.domain, self.report_slug, self.subreport_slug
            )
        except UnsupportedSavedReportError:
            return None

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
        if self.date_range == 'lastmonth':
            return "Last Month"
        elif self.days and not self.start_date:
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

    def get_report_content(self, lang, attach_excel=False):
        """
        Get the report's HTML content as rendered by the static view format.

        """
        try:
            if self.report is None:
                return ReportContent(
                    _("The report used to create this scheduled report is no"
                      " longer available on CommCare HQ.  Please delete this"
                      " scheduled report and create a new one using an available"
                      " report."),
                    None,
                )
        except Exception:
            pass

        from django.http import HttpRequest, QueryDict
        mock_request = HttpRequest()
        mock_request.couch_user = self.owner
        mock_request.user = self.owner.get_django_user()
        mock_request.domain = self.domain
        mock_request.couch_user.current_domain = self.domain
        mock_request.couch_user.language = lang
        mock_request.method = 'GET'

        mock_query_string_parts = [self.query_string, 'filterSet=true']
        if self.is_configurable_report:
            mock_query_string_parts.append(urlencode(self.filters, True))
            mock_query_string_parts.append(urlencode(self.get_date_range(), True))
        mock_request.GET = QueryDict('&'.join(mock_query_string_parts))

        # Make sure the request gets processed by PRBAC Middleware
        CCHQPRBACMiddleware.apply_prbac(mock_request)

        try:
            dispatch_func = functools.partial(self._dispatcher.__class__.as_view(), mock_request, **self.view_kwargs)
            email_response = dispatch_func(render_as='email')
            if email_response.status_code == 302:
                return ReportContent(
                    _(
                        "We are sorry, but your saved report '%(config_name)s' "
                        "is no longer accessible because the owner %(username)s "
                        "is no longer active."
                    ) % {
                        'config_name': self.name,
                        'username': self.owner.username
                    },
                    None,
                )
            return ReportContent(
                json.loads(email_response.content)['report'],
                dispatch_func(render_as='excel') if attach_excel else None,
            )
        except PermissionDenied:
            return ReportContent(
                _(
                    "We are sorry, but your saved report '%(config_name)s' "
                    "is no longer accessible because your subscription does "
                    "not allow Custom Reporting. Please talk to your Project "
                    "Administrator about enabling Custom Reports. If you "
                    "want CommCare HQ to stop sending this message, please "
                    "visit %(saved_reports_url)s to remove this "
                    "Emailed Report."
                ) % {
                    'config_name': self.name,
                    'saved_reports_url': absolute_reverse(
                        'saved_reports', args=[mock_request.domain]
                    ),
                },
                None,
            )
        except Http404:
            return ReportContent(
                _(
                    "We are sorry, but your saved report '%(config_name)s' "
                    "can not be generated since you do not have the correct permissions. "
                    "Please talk to your Project Administrator about getting permissions for this"
                    "report."
                ) % {
                    'config_name': self.name,
                },
                None,
            )
        except UnsupportedSavedReportError:
            return ReportContent(
                _(
                    "We are sorry, but your saved report '%(config_name)s' "
                    "is no longer available. If you think this is a mistake, please report an issue."
                ) % {
                    'config_name': self.name,
                },
                None,
            )
        except Exception:
            notify_exception(None, "Error generating report: {}".format(self.report_slug), details={
                'domain': self.domain,
                'user': self.owner.username,
                'report': self.report_slug,
                'report config': self.get_id
            })
            return ReportContent(_("An error occurred while generating this report."), None)

    @property
    def is_configurable_report(self):
        from corehq.apps.userreports.reports.view import ConfigurableReport
        return self.report_type == ConfigurableReport.prefix

    @property
    @memoized
    def languages(self):
        if self.is_configurable_report:
            return frozenset(self.report.spec.get_languages())
        return frozenset()

    @property
    @memoized
    def configurable_report(self):
        from corehq.apps.userreports.reports.view import ConfigurableReport
        return ConfigurableReport.get_report(
            self.domain, self.report_slug, self.subreport_slug
        )

    @property
    def datespan_filters(self):
        return (self.configurable_report.datespan_filters
                if self.is_configurable_report else [])

    @property
    def has_ucr_datespan(self):
        return self.is_configurable_report and self.datespan_filters

    @staticmethod
    def datespan_filter_choices(datespan_filters, lang):
        localized_datespan_filters = []
        for f in datespan_filters:
            copy = dict(f)
            copy['display'] = ucr_localize(copy['display'], lang)
            localized_datespan_filters.append(copy)

        with localize(lang):
            return [{
                'display': _('Choose a date filter...'),
                'slug': None,
            }] + localized_datespan_filters

DEFAULT_REPORT_NOTIF_SUBJECT = "Scheduled report from CommCare HQ"


class ReportNotification(CachedCouchDocumentMixin, Document):
    domain = StringProperty()
    owner_id = StringProperty()

    recipient_emails = StringListProperty()
    config_ids = StringListProperty()
    send_to_owner = BooleanProperty()
    attach_excel = BooleanProperty()
    # language is only used if some of the config_ids refer to UCRs.
    language = StringProperty()
    email_subject = StringProperty(default=DEFAULT_REPORT_NOTIF_SUBJECT)

    hour = IntegerProperty(default=8)
    minute = IntegerProperty(default=0)
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
                                        include_docs=True, startkey=key, endkey=key + [{}],
                                        wrapper=cls.wrap, **kwargs)
        return result

    @property
    @memoized
    def all_recipient_emails(self):
        # handle old documents
        if not self.owner_id:
            return frozenset([self.owner.get_email()])

        emails = frozenset(self.recipient_emails)
        if self.send_to_owner and self.owner_email:
            emails |= {self.owner_email}
        return emails

    @property
    @memoized
    def owner_email(self):
        if self.owner.is_web_user():
            return self.owner.username

        email = self.owner.get_email()
        try:
            validate_email(email)
            return email
        except Exception:
            pass

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

            def _sort_key(config_id):
                if config_id in self.config_ids:
                    return self.config_ids.index(config_id)
                else:
                    return len(self.config_ids)
            configs = sorted(configs, key=_sort_key)
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

        return tuple(configs)

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

    @property
    @memoized
    def recipients_by_language(self):
        user_languages = {
            user['username']: user['language']
            for user in get_user_docs_by_username(self.all_recipient_emails)
            if 'username' in user and 'language' in user
        }
        fallback_language = user_languages.get(self.owner_email, 'en')

        recipients = defaultdict(list)
        for email in self.all_recipient_emails:
            language = user_languages.get(email, fallback_language)
            recipients[language].append(email)
        return immutabledict(recipients)

    def send(self):
        # Scenario: user has been removed from the domain that they
        # have scheduled reports for.  Delete this scheduled report
        if not self.owner.is_member_of(self.domain):
            self.delete()
            return

        if self.owner.is_deleted():
            self.delete()
            return

        if self.recipients_by_language:
            for language, emails in self.recipients_by_language.items():
                self._get_and_send_report(language, emails)

    def _get_and_send_report(self, language, emails):
        from corehq.apps.reports.views import get_scheduled_report_response

        with localize(language):
            title = (
                _(DEFAULT_REPORT_NOTIF_SUBJECT)
                if self.email_subject == DEFAULT_REPORT_NOTIF_SUBJECT
                else self.email_subject
            )
            attach_excel = getattr(self, 'attach_excel', False)
            body, excel_files = get_scheduled_report_response(
                self.owner, self.domain, self._id, attach_excel=attach_excel
            )
            for email in emails:
                send_html_email_async.delay(title, email, body.content,
                                            email_from=settings.DEFAULT_FROM_EMAIL,
                                            file_attachments=excel_files)


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

    @classmethod
    def get_stale_exports(cls, domain):
        return [
            cls.wrap(export)
            for export in stale_get_exports_json(domain)
            if export['type'] == cls._default_type
        ]


class FormExportSchema(HQExportSchema):
    doc_type = 'SavedExportSchema'
    app_id = StringProperty()
    include_errors = BooleanProperty(default=False)
    split_multiselects = BooleanProperty(default=False)
    _default_type = 'form'

    def update_schema(self):
        super(FormExportSchema, self).update_schema()
        if self.split_multiselects:
            self.update_question_schema()
            for column in [column for table in self.tables for column in table.columns]:
                if isinstance(column, SplitColumn):
                    question = self.question_schema.question_schema.get(column.index)
                    # this is to workaround a bug where a "special" column was incorrectly
                    # being flagged as a SplitColumn.
                    # https://github.com/dimagi/commcare-hq/pull/9915
                    if question:
                        column.options = question.options
                        column.ignore_extras = True

    def update_question_schema(self):
        schema = self.question_schema
        schema.update_schema()

    @property
    def question_schema(self):
        return FormQuestionSchema.get_or_create(self.domain, self.app_id, self.xmlns)

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
        user_ids.add('demo_user')

        def _top_level_filter(form):
            # careful, closures used
            return form_matches_users(form, user_ids) or is_commconnect_form(form)

        f = SerializableFunction(_top_level_filter)
        if self.app_id is not None:
            from corehq.apps.reports import util as reports_util
            f.add(reports_util.app_export_filter, app_id=self.app_id)
        if not self.include_errors:
            f.add(instances)
        actual = SerializableFunction(default_form_filter, filter=f)
        return actual

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
            if not question['value']:  # question probably belongs to a broken form
                continue
            index_parts = question['value'].split('/')
            assert index_parts[0] == ''
            index_parts[1] = 'form'
            index = '.'.join(index_parts[1:])
            order.append(index)

        return order

    def get_default_order(self):
        return {'#': self.question_order}

    def uses_cases(self):
        if not self.app or isinstance(self.app, RemoteApp):
            return False
        form = self.app.get_form_by_xmlns(self.xmlns)
        if form and isinstance(form, Form):
            return bool(form.active_actions())
        return False


class CaseExportSchema(HQExportSchema):
    doc_type = 'SavedExportSchema'
    _default_type = 'case'

    @property
    def filter(self):
        return SerializableFunction(default_case_filter)

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
            prop_map = get_case_properties(app, [self.case_type], defaults=("name",))
            props |= set(prop_map[self.case_type])

        return props


class DefaultFormExportSchema(DefaultExportSchema):

    def remap_tables(self, tables):
        # kill the weird confusing stuff, and rename the main table to something sane
        tables = _apply_removal(tables, ('#|#export_tag|#', '#|location_|#', '#|history|#'))
        return _apply_mapping(tables, {
            '#': 'Forms',
        })


def _apply_mapping(export_tables, mapping_dict):
    def _clean(tabledata):
        def _clean_tablename(tablename):
            return mapping_dict.get(tablename, tablename)
        return (_clean_tablename(tabledata[0]), tabledata[1])
    return map(_clean, export_tables)


def _apply_removal(export_tables, removal_list):
    return [tabledata for tabledata in export_tables if not tabledata[0] in removal_list]


class HQGroupExportConfiguration(QuickCachedDocumentMixin, GroupExportConfiguration):
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
                    'case': CaseExportSchema,
                }[export.type].wrap(export._doc)
            except KeyError:
                return export

        for custom in list(self.custom_export_ids):
            custom_export = self._get_custom(custom)
            if custom_export:
                yield _rewrap(custom_export)

    def exports_of_type(self, type):
        return self._saved_exports_from_configs([
            config for config, schema in self.all_exports if schema.type == type
        ])

    @property
    @memoized
    def form_exports(self):
        return self.exports_of_type('form')

    @property
    @memoized
    def case_exports(self):
        return self.exports_of_type('case')

    @classmethod
    @quickcache(['cls.__name__', 'domain'])
    def by_domain(cls, domain):
        return hq_group_export_configs_by_domain(domain)

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

    def clear_caches(self):
        super(HQGroupExportConfiguration, self).clear_caches()
        self.by_domain.clear(self.__class__, self.domain)
