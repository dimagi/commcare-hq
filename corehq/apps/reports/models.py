from datetime import datetime, timedelta
import logging
from django.core.urlresolvers import reverse
from django.http import Http404
from django.utils import html
from django.utils.safestring import mark_safe
import pytz
from corehq import Domain
from corehq.apps import reports
from corehq.apps.app_manager.models import get_app, Form, RemoteApp
from corehq.apps.app_manager.util import ParentCasePropertyBuilder
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from corehq.apps.domain.middleware import CCHQPRBACMiddleware
from corehq.apps.export.models import FormQuestionSchema
from corehq.apps.reports.display import xmlns_to_name
from couchdbkit.ext.django.schema import *
from corehq.apps.reports.exportfilters import form_matches_users, is_commconnect_form, default_form_filter, \
    default_case_filter
from corehq.apps.users.models import WebUser, CommCareUser, CouchUser
from corehq.feature_previews import CALLCENTER
from corehq.util.view_utils import absolute_reverse
from couchexport.models import SavedExportSchema, GroupExportConfiguration, FakeSavedExportSchema
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
from dimagi.utils.web import get_url_base
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
                      ugettext_noop("CommTrack")]
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


DATE_RANGE_CHOICES = ['last7', 'last30', 'lastn', 'lastmonth', 'since', 'range']


class ReportConfig(CachedCouchDocumentMixin, Document):
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
        from corehq.apps.userreports.reports.view import ConfigurableReport

        dispatchers = [
            ProjectReportDispatcher,
            CustomProjectReportDispatcher,
            ADMSectionDispatcher,
            ConfigurableReport,
        ]

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
        from dateutil.relativedelta import relativedelta
        today = datetime.date.today()
        if date_range == 'since':
            start_date = self.start_date
            end_date = today
        elif date_range == 'range':
            start_date = self.start_date
            end_date = self.end_date
        elif date_range == 'lastmonth':
            end_date = today
            start_date = today - relativedelta(months=1) + timedelta(days=1)  # add one day to handle inclusiveness
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

        if start_date is None or end_date is None:
            # this is due to bad validation. see: http://manage.dimagi.com/default.asp?110906
            logging.error('scheduled report %s is in a bad state (no startdate or enddate)' % self._id)
            return {}

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
        return self._dispatcher.get_report(
            self.domain, self.report_slug, self.subreport_slug
        )

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

    def get_report_content(self, attach_excel=False):
        """
        Get the report's HTML content as rendered by the static view format.

        """
        try:
            if self.report is None:
                return _("The report used to create this scheduled report is no"
                         " longer available on CommCare HQ.  Please delete this"
                         " scheduled report and create a new one using an available"
                         " report."), None
        except Exception:
            pass

        from django.http import HttpRequest, QueryDict
        request = HttpRequest()
        request.couch_user = self.owner
        request.user = self.owner.get_django_user()
        request.domain = self.domain
        request.couch_user.current_domain = self.domain

        request.GET = QueryDict(self.query_string + '&filterSet=true')

        # Make sure the request gets processed by PRBAC Middleware
        CCHQPRBACMiddleware.apply_prbac(request)

        try:
            from corehq.apps.userreports.reports.view import ConfigurableReport
            if type(self._dispatcher) == ConfigurableReport:
                response = self._dispatcher.dispatch(request, self.subreport_slug, render_as='email',
                    **self.view_kwargs)
            else:
                response = self._dispatcher.dispatch(request, render_as='email',
                    **self.view_kwargs)
            if attach_excel is True:
                file_obj = self._dispatcher.dispatch(request, render_as='excel',
                **self.view_kwargs)
            else:
                file_obj = None
            return json.loads(response.content)['report'], file_obj
        except PermissionDenied:
            return _(
                "We are sorry, but your saved report '%(config_name)s' "
                "is no longer accessible because your subscription does "
                "not allow Custom Reporting. Please talk to your Project "
                "Administrator about enabling Custom Reports. If you "
                "want CommCare HQ to stop sending this message, please "
                "visit %(saved_reports_url)s to remove this "
                "Emailed Report."
            ) % {
                'config_name': self.name,
                'saved_reports_url': absolute_reverse('saved_reports',
                                                      args=[request.domain]),
            }, None
        except Http404:
            return _("We are sorry, but your saved report '%(config_name)s' "
                     "can not be generated since you do not have the correct permissions. "
                     "Please talk to your Project Administrator about getting permissions for this"
                     "report.") % {'config_name': self.name}, None
        except Exception:
            notify_exception(None, "Error generating report: {}".format(self.report_slug), details={
                'domain': self.domain,
                'user': self.owner.username,
                'report': self.report_slug,
                'report config': self.get_id
            })
            return _("An error occurred while generating this report."), None


class UnsupportedScheduledReportError(Exception):
    pass


class ReportNotification(CachedCouchDocumentMixin, Document):
    domain = StringProperty()
    owner_id = StringProperty()

    recipient_emails = StringListProperty()
    config_ids = StringListProperty()
    send_to_owner = BooleanProperty()
    attach_excel = BooleanProperty()

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
            if hasattr(self, "attach_excel"):
                attach_excel = self.attach_excel
            else:
                attach_excel = False
            body, excel_files = get_scheduled_report_response(self.owner, self.domain, self._id, attach_excel=attach_excel)
            for email in self.all_recipient_emails:
                send_HTML_email(title, email, body.content, email_from=settings.DEFAULT_FROM_EMAIL, file_attachments=excel_files)


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

    def update_schema(self):
        super(FormExportSchema, self).update_schema()
        self.update_question_schema()

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
            f.add(reports.util.app_export_filter, app_id=self.app_id)
        if not self.include_errors:
            f.add(couchforms.filters.instances)
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

        if CALLCENTER.enabled(self.domain):
            from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
            user_fields = CustomDataFieldsDefinition.get_or_create(self.domain, 'UserFields')
            props |= {field.slug for field in user_fields.fields}

        for app in self.applications:
            builder = ParentCasePropertyBuilder(app, ("name",))
            props |= set(builder.get_properties(self.case_type))

        return props


class FakeFormExportSchema(FakeSavedExportSchema):

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


class HQGroupExportConfiguration(CachedCouchDocumentMixin, GroupExportConfiguration):
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
    def by_domain(cls, domain):
        return cache_core.cached_view(cls.get_db(), "groupexport/by_domain",
            key=domain,
            reduce=False,
            include_docs=True,
            wrapper=cls.wrap,
        )

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
