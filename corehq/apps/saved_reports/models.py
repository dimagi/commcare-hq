import calendar

from django.utils.safestring import mark_safe
from corehq.apps.enterprise.dispatcher import EnterpriseReportDispatcher
import functools
import hashlib
import json
import logging
import uuid
from collections import defaultdict, namedtuple
from datetime import datetime
from couchdbkit.exceptions import ResourceNotFound

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.http import Http404, HttpRequest, QueryDict
from django.utils.translation import gettext as _

from couchdbkit.ext.django.schema import (
    BooleanProperty,
    DateProperty,
    DictProperty,
    IntegerProperty,
    StringListProperty,
    StringProperty,
)
from django_prbac.exceptions import PermissionDenied
from memoized import memoized
from six.moves.urllib.parse import urlencode
from sqlalchemy.util import immutabledict

from dimagi.ext.couchdbkit import Document
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.dates import DateSpan
from dimagi.utils.django.email import LARGE_FILE_SIZE_ERROR_CODES
from dimagi.utils.logging import notify_exception
from dimagi.utils.web import json_request

from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from corehq.apps.domain.middleware import CCHQPRBACMiddleware
from dimagi.utils.django.email import send_HTML_email
from corehq.apps.reports.daterange import (
    get_all_daterange_slugs,
    get_daterange_start_end_dates,
)
from corehq.apps.reports.dispatcher import (
    CustomProjectReportDispatcher,
    ProjectReportDispatcher,
    ReleaseManagementReportDispatcher,
)
from corehq.apps.reports.exceptions import InvalidDaterangeException
from corehq.apps.reports.tasks import export_all_rows_task
from corehq.apps.saved_reports.exceptions import (
    UnsupportedSavedReportError,
    UnsupportedScheduledReportError,
)
from corehq.apps.userreports.util import \
    default_language as ucr_default_language
from corehq.apps.userreports.util import localize as ucr_localize
from corehq.apps.users.dbaccessors import get_user_docs_by_username
from corehq.apps.users.models import CouchUser
from corehq.elastic import ESError
from corehq.util.translation import localize
from corehq.util.view_utils import absolute_reverse

from smtplib import SMTPSenderRefused

from .logging import ScheduledReportLogger
from corehq.util.quickcache import quickcache

ReportContent = namedtuple('ReportContent', ['text', 'attachment'])
DEFAULT_REPORT_NOTIF_SUBJECT = "Scheduled report from CommCare HQ"


class ReportConfig(CachedCouchDocumentMixin, Document):
    """
    This model represents a "Saved Report." That is, a saved set of filters for a given report.
    """

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
                            stale=True, skip=None, limit=None, include_shared=False):
        kwargs = {}
        if stale:
            kwargs['stale'] = settings.COUCH_STALE_QUERY

        if report_slug is not None:
            key = ["name slug", domain, owner_id, report_slug]
        else:
            key = ["name", domain, owner_id]

        db = cls.get_db()
        if skip is not None:
            kwargs['skip'] = skip
        if limit is not None:
            kwargs['limit'] = limit

        configs = cache_core.cached_view(
            db,
            "reportconfig/configs_by_domain",
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key + [{}],
            wrapper=cls.wrap,
            **kwargs
        )

        if include_shared:
            user_configs_ids = [c._id for c in configs]
            shared_configs = [c for c in cls.shared_on_domain(domain) if c._id not in user_configs_ids]
            configs = configs + shared_configs

        return configs

    @classmethod
    @quickcache(['domain', 'only_id'], timeout=1 * 60 * 60)
    def shared_on_domain(cls, domain, only_id=False):
        shared_config_ids = {
            id_ for rn in ReportNotification.by_domain(domain, stale=False)
            for id_ in rn.config_ids
        }
        if only_id:
            return shared_config_ids
        else:
            return {ReportConfig.get(config_id) for config_id in shared_config_ids}

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
            'report_creator': self.owner.username,
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
            ConfigurableReportView,
            CustomConfigurableReportDispatcher,
        )
        from corehq.apps.geospatial.dispatchers import CaseManagementMapDispatcher

        dispatchers = [
            ProjectReportDispatcher,
            CustomProjectReportDispatcher,
            EnterpriseReportDispatcher,
            ReleaseManagementReportDispatcher,
            CaseManagementMapDispatcher
        ]

        for dispatcher in dispatchers:
            if dispatcher.prefix == self.report_type:
                return dispatcher()

        if self.report_type == 'configurable':
            if self.subreport_slug.startswith(CUSTOM_REPORT_PREFIX):
                return CustomConfigurableReportDispatcher()
            else:
                return ConfigurableReportView()

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
            if self.is_configurable_report:
                url_base = absolute_reverse(self.report_slug, args=[self.domain, self.subreport_slug])
            else:
                url_base = absolute_reverse(self._dispatcher.name(), kwargs=self.url_kwargs)
            return url_base + '?' + self.query_string
        except UnsupportedSavedReportError:
            return "#"
        except Exception as e:
            logging.exception(str(e))
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
        return CouchUser.get_by_user_id(self.owner_id)

    def get_report_content(self, lang, attach_excel=False, couch_user=None, subreport_slug=None):
        """
        Get the report's HTML content as rendered by the static view format.

        """
        from corehq.apps.locations.middleware import LocationAccessMiddleware
        from corehq.apps.userreports.reports.util import report_has_location_filter
        from corehq import toggles

        if couch_user is None:
            couch_user = self.owner

        if ((not toggles.LOCATION_RESTRICTED_SCHEDULED_REPORTS.enabled(self.domain)
                or not report_has_location_filter(subreport_slug, self.domain)
                or not couch_user.get_location_ids(self.domain))
                and not couch_user.has_permission(self.domain, 'access_all_locations')):
            return ReportContent(_("This project has restricted data access rules. \
                                                 Please contact your project administrator to be assigned access \
                                                 to data in this project."),
                                 None, )

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

        if getattr(self.report, 'is_deprecated', False):
            return ReportContent(
                self.report.deprecation_email_message
                or _("[DEPRECATED] %s report has been deprecated and will stop working soon. "
                     "Please update your saved reports email settings if needed." % self.report.name
                     ),
                None,
            )

        mock_request = HttpRequest()
        mock_request.couch_user = couch_user
        mock_request.user = couch_user.get_django_user()
        mock_request.domain = self.domain
        mock_request.couch_user.current_domain = self.domain
        mock_request.couch_user.language = lang
        mock_request.method = 'GET'
        mock_request.bypass_two_factor = True

        mock_query_string_parts = [self.query_string, 'filterSet=true']
        mock_request.GET = QueryDict('&'.join(mock_query_string_parts))

        # Make sure the request gets processed by PRBAC Middleware
        CCHQPRBACMiddleware.apply_prbac(mock_request)
        LocationAccessMiddleware.apply_location_access(mock_request)

        try:
            dispatch_func = functools.partial(self._dispatcher.__class__.as_view(),
                                              mock_request, **self.view_kwargs)
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
            try:
                content_json = json.loads(email_response.content)
            except ValueError:
                email_text = email_response.content
            else:
                email_text = content_json['report']

            email_html = mark_safe(email_text)  # nosec: this is HTML we generate
            excel_attachment = dispatch_func(render_as='excel') if attach_excel else None
            return ReportContent(email_html, excel_attachment)
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

    @property
    def is_active(self):
        """
        Returns True if the report has a start_date that is in the past or there is
        no start date
        :return: boolean
        """
        return self.start_date is None or self.start_date <= datetime.today().date()

    @property
    def is_configurable_report(self):
        from corehq.apps.userreports.reports.view import ConfigurableReportView
        return self.report_type == ConfigurableReportView.prefix

    @property
    def supports_translations(self):
        if self.report_type == CustomProjectReportDispatcher.prefix:
            return self.report.get_supports_translations()
        else:
            return self.is_configurable_report

    @property
    @memoized
    def languages(self):
        if self.is_configurable_report:
            return frozenset(self.report.spec.get_languages())
        elif self.supports_translations:
            return frozenset(self.report.languages)
        return frozenset()

    @property
    @memoized
    def configurable_report(self):
        from corehq.apps.userreports.reports.view import ConfigurableReportView
        return ConfigurableReportView.get_report(
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

    def is_shared_on_domain(self):
        config_ids = self.shared_on_domain(self.domain, only_id=True)
        return self._id in config_ids


class ReportNotification(CachedCouchDocumentMixin, Document):
    domain = StringProperty()
    owner_id = StringProperty()

    recipient_emails = StringListProperty()
    config_ids = StringListProperty()
    send_to_owner = BooleanProperty()
    attach_excel = BooleanProperty()
    # language is only used if some of the config_ids refer to UCRs or custom reports
    language = StringProperty()
    email_subject = StringProperty(default=DEFAULT_REPORT_NOTIF_SUBJECT)

    hour = IntegerProperty(default=8)
    minute = IntegerProperty(default=0)  # Currently unused
    # Used for the "hourly" interval to enable hourly range functionality
    stop_hour = IntegerProperty(default=23)
    stop_minute = IntegerProperty(default=0)  # Currently unused

    day = IntegerProperty(default=1)
    interval = StringProperty(choices=["hourly", "daily", "weekly", "monthly"])
    uuid = StringProperty()
    start_date = DateProperty(default=None)

    addedToBulk = BooleanProperty(default=False)

    @property
    def is_editable(self):
        try:
            self.report_slug
            return False
        except AttributeError:
            return True

    @classmethod
    def get_report(cls, report_id):
        try:
            notification = ReportNotification.get(report_id)
        except ResourceNotFound:
            notification = None
        else:
            if notification.doc_type != 'ReportNotification':
                notification = None

        return notification

    @classmethod
    def by_domain(cls, domain, stale=True, **kwargs):
        if stale:
            kwargs['stale'] = settings.COUCH_STALE_QUERY

        key = [domain]
        return cls._get_view_by_key(key, **kwargs)

    @classmethod
    def by_domain_and_owner(cls, domain, owner_id, stale=True, **kwargs):
        if stale:
            kwargs['stale'] = settings.COUCH_STALE_QUERY

        key = [domain, owner_id]
        return cls._get_view_by_key(key, **kwargs)

    @classmethod
    def _get_view_by_key(cls, key, **kwargs):
        db = cls.get_db()
        result = cache_core.cached_view(db, "reportconfig/user_notifications", reduce=False,
                                        include_docs=True, startkey=key, endkey=key + [{}],
                                        wrapper=cls.wrap, **kwargs)
        return result

    @property
    @memoized
    def all_recipient_emails(self):
        emails = frozenset(self.recipient_emails)
        if self.send_to_owner and self.owner_email:
            emails |= {self.owner_email}
        return emails

    @property
    @memoized
    def owner_email(self):
        if self.owner is None:
            return None
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
        return CouchUser.get_by_user_id(id)

    @property
    @memoized
    def configs(self):
        """
        Access the notification's associated configs as a list, transparently
        returning an appropriate dummy for old notifications which have
        `report_slug` instead of `config_ids`.
        """
        if self.config_ids:
            configs = []
            for config_doc in iter_docs(ReportConfig.get_db(), self.config_ids):
                config = ReportConfig.wrap(config_doc)
                if not hasattr(config, 'deleted'):
                    configs.append(config)

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
        if self.interval == 'hourly':
            return _("Every hour")
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
        if self.language:
            fallback_language = self.language
        else:
            fallback_language = user_languages.get(self.owner_email, 'en')

        recipients = defaultdict(list)
        for email in self.all_recipient_emails:
            language = user_languages.get(email, fallback_language) or fallback_language
            recipients[language].append(email)
        return immutabledict(recipients)

    def get_secret(self, email):
        uuid = self._get_or_create_uuid()
        return hashlib.sha1((uuid + email).encode('utf-8')).hexdigest()[:20]

    def send(self):
        # Scenario: user has been removed from the domain that they
        # have scheduled reports for.  Delete this scheduled report
        if not self.owner.is_member_of(self.domain, allow_enterprise=True):
            self.delete()
            return

        if self.owner.is_deleted():
            self.delete()
            return

        if self.recipients_by_language:
            for language, emails in self.recipients_by_language.items():
                self._get_and_send_report(language, emails)

    def _get_or_create_uuid(self):
        if not self.uuid:
            self.uuid = uuid.uuid4().hex
            self.save()
        return self.uuid

    def _get_and_send_report(self, language, emails):
        with localize(language):
            title = self._get_title(self.email_subject)

            attach_excel = getattr(self, 'attach_excel', False)
            report_text, excel_files = self._generate_report(attach_excel, title, emails)

            # Both are empty if ALL the ReportConfigs in the ReportNotification
            # have a start_date in the future (or an exception occurred)
            if not report_text and not excel_files:
                return

            self._send_emails(title, report_text, emails, excel_files)

    @staticmethod
    def _get_title(subject):
        # only translate the default subject
        return (
            _(DEFAULT_REPORT_NOTIF_SUBJECT)
            if subject == DEFAULT_REPORT_NOTIF_SUBJECT
            else subject
        )

    def _generate_report(self, attach_excel, title, emails):
        from corehq.apps.reports.views import get_scheduled_report_response
        report_text = None
        excel_files = None

        try:
            report_text, excel_files = get_scheduled_report_response(
                self.owner, self.domain, self._id, attach_excel=attach_excel,
                send_only_active=True
            )
        # TODO: Be more specific with our error-handling. If building the report could fail,
        # we should have a reasonable idea of why
        except Exception as er:
            notify_exception(
                None,
                message="Encountered error while generating report",
                details={
                    'subject': title,
                    'recipients': str(emails),
                    'error': er,
                }
            )
            if isinstance(er, ESError):
                # An ElasticSearch error could indicate that the report itself is too large.
                # Try exporting the report instead, as that builds the report in chunks,
                # rather than all at once.
                # TODO: narrow down this handling so that we don't try this if ElasticSearch is simply down,
                # for example
                self._export_report(emails, title)
        return report_text, excel_files

    def _send_emails(self, title, report_text, emails, excel_files):
        from corehq.apps.reports.views import render_full_report_notification

        email_is_too_large = False

        for email in emails:
            body = render_full_report_notification(None, report_text, email, self).content
            try:
                self._send_email(title, email, body, excel_files)
            except Exception as er:
                if isinstance(er, SMTPSenderRefused) and (er.smtp_code in LARGE_FILE_SIZE_ERROR_CODES):
                    email_is_too_large = True
                    break
                else:
                    ScheduledReportLogger.log_email_failure(self, email, body, er)
            else:
                ScheduledReportLogger.log_email_success(self, email, body)

        if email_is_too_large:
            # TODO: Because different domains may have different size thresholds,
            # one of the middle addresses could have triggered this, causing us to send
            # both the original email and the retried email to some users.
            # This is likely best handled by treating each address separately.
            ScheduledReportLogger.log_email_size_failure(self, email, emails, body)
            # The body is too large -- attempt to resend the report as attachments.
            if excel_files:
                # If the attachments already exist, just send them
                self._send_only_attachments(title, emails, excel_files)
            else:
                # Otherwise we're forced to trigger a process to create them
                self._export_report(emails, title)

    def _send_email(self, title, email, body, excel_files):
        send_HTML_email(
            title, email, body,
            file_attachments=excel_files,
            smtp_exception_skip_list=LARGE_FILE_SIZE_ERROR_CODES,
            domain=self.domain,
            use_domain_gateway=True,)

    def _send_only_attachments(self, title, emails, excel_files):
        message = _("Unable to generate email report. Excel files are attached.")
        send_HTML_email(
            title,
            emails,
            message,
            file_attachments=excel_files,
            domain=self.domain,
            use_domain_gateway=True,
        )

    def _export_report(self, emails, title):
        from corehq.apps.reports.standard.deployments import ApplicationStatusReport

        for report_config in self.configs:
            mock_request = HttpRequest()
            mock_request.couch_user = self.owner
            mock_request.user = self.owner.get_django_user()
            mock_request.domain = self.domain
            mock_request.couch_user.current_domain = self.domain
            mock_request.couch_user.language = self.language
            mock_request.method = 'GET'
            mock_request.bypass_two_factor = True

            mock_query_string_parts = [report_config.query_string, 'filterSet=true']
            mock_request.GET = QueryDict('&'.join(mock_query_string_parts))
            request_data = vars(mock_request)
            request_data['couch_user'] = mock_request.couch_user.userID
            if report_config.report_slug != ApplicationStatusReport.slug:
                # ApplicationStatusReport doesn't have date filter
                date_range = report_config.get_date_range()
                start_date = datetime.strptime(date_range['startdate'], '%Y-%m-%d')
                end_date = datetime.strptime(date_range['enddate'], '%Y-%m-%d')
                datespan = DateSpan(start_date, end_date)
                request_data['datespan'] = datespan

            full_request = {'request': request_data,
                            'domain': request_data['domain'],
                            'context': {},
                            'request_params': json_request(request_data['GET'])}

            export_all_rows_task(report_config.report, full_request, emails, title)

    def remove_recipient(self, email):
        try:
            if email == self.owner.get_email():
                self.send_to_owner = False
            self.recipient_emails.remove(email)
        except ValueError:
            pass

    def update_attributes(self, items):
        for k, v in items:
            if k == 'start_date':
                self.verify_start_date(v)
            self.__setattr__(k, v)

    def verify_start_date(self, start_date):
        if start_date != self.start_date and start_date < datetime.today().date():
            raise ValidationError("You can not specify a start date in the past.")

    def can_be_viewed_by(self, user):
        return ((user._id == self.owner_id)
                or (user.is_domain_admin(self.domain)
                or (user.get_email() in self.all_recipient_emails)))


class ScheduledReportsCheckpoint(models.Model):
    """
    Each time a date range is checked for scheduled reports to send
    a ScheduledReportsCheckpoint is created to mark that.
    This allows us to achieve full non-overlapping coverage of time as it unfolds,
    even in the face of varying promptness and uptime in celery and celery beat.
    Secondarily, it also leaves a positive record of when a time batch was processed.
    """
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(db_index=True)

    @classmethod
    def get_latest(cls):
        try:
            return cls.objects.order_by('-end_datetime')[0]
        except IndexError:
            return None


class ScheduledReportLog(models.Model):
    LOG_STATE_SUCCESS = 'success'
    LOG_STATE_ERROR = 'error'
    LOG_STATE_RETRY = 'retry'

    sent_to = models.EmailField(db_index=True)
    domain = models.CharField(max_length=255, db_index=True)
    report_id = models.UUIDField(db_index=True)
    state = models.CharField(max_length=10)
    size = models.PositiveIntegerField()
    timestamp = models.DateTimeField(default=datetime.utcnow, db_index=True)
    error = models.TextField(null=True)

    def __repr__(self):
        return f'{self.report_id} sent to {self.sent_to}: {self.state}'
