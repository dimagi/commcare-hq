from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy, ugettext_noop

from dateutil.parser import parse
from memoized import memoized

from auditcare.models import NavigationEventAudit
from auditcare.utils.export import navigation_event_ids_by_user
from dimagi.utils.couch.database import iter_docs
from phonelog.models import DeviceReportEntry
from phonelog.reports import BaseDeviceLogReport

from corehq.apps.es import users as user_es
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin
from corehq.apps.reports.standard.sms import PhoneNumberReport
from corehq.apps.sms.filters import RequiredPhoneNumberFilter
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.models import PhoneNumber
from corehq.const import SERVER_DATETIME_FORMAT


class AdminReport(GenericTabularReport):
    dispatcher = AdminReportDispatcher

    base_template = "hqadmin/faceted_report.html"
    report_template_path = "reports/tabular.html"
    section_name = ugettext_noop("ADMINREPORT")
    default_params = {}
    is_admin_report = True


class DeviceLogSoftAssertReport(BaseDeviceLogReport, AdminReport):
    base_template = 'reports/base_template.html'

    slug = 'device_log_soft_asserts'
    name = ugettext_lazy("Global Device Logs Soft Asserts")

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.devicelog.DeviceLogDomainFilter',
        'corehq.apps.reports.filters.devicelog.DeviceLogCommCareVersionFilter',
    ]
    emailable = False
    default_rows = 10

    _username_fmt = "%(username)s"
    _device_users_fmt = "%(username)s"
    _device_id_fmt = "%(device)s"
    _log_tag_fmt = "<label class='%(classes)s'>%(text)s</label>"

    @property
    def selected_domain(self):
        selected_domain = self.request.GET.get('domain', None)
        return selected_domain if selected_domain != '' else None

    @property
    def selected_commcare_version(self):
        commcare_version = self.request.GET.get('commcare_version', None)
        return commcare_version if commcare_version != '' else None

    @property
    def headers(self):
        headers = super(DeviceLogSoftAssertReport, self).headers
        headers.add_column(DataTablesColumn("Domain"))
        return headers

    @property
    def rows(self):
        logs = self._filter_logs()
        rows = self._create_rows(
            logs,
            range=slice(self.pagination.start, self.pagination.start + self.pagination.count)
        )
        return rows

    def _filter_logs(self):
        logs = DeviceReportEntry.objects.filter(
            date__range=[self.datespan.startdate_param_utc, self.datespan.enddate_param_utc]
        ).filter(type='soft-assert')

        if self.selected_domain is not None:
            logs = logs.filter(domain__exact=self.selected_domain)

        if self.selected_commcare_version is not None:
            logs = logs.filter(app_version__contains='"{}"'.format(self.selected_commcare_version))

        return logs

    def _create_row(self, log, *args, **kwargs):
        row = super(DeviceLogSoftAssertReport, self)._create_row(log, *args, **kwargs)
        row.append(log.domain)
        return row


class AdminPhoneNumberReport(PhoneNumberReport):
    name = ugettext_lazy("Admin Phone Number Report")
    slug = 'phone_number_report'
    fields = [
        RequiredPhoneNumberFilter,
    ]

    dispatcher = AdminReportDispatcher
    default_report_url = '#'
    is_admin_report = True

    @property
    def shared_pagination_GET_params(self):
        return [
            {
                'name': RequiredPhoneNumberFilter.slug,
                'value': RequiredPhoneNumberFilter.get_value(self.request, domain=None)
            },
        ]

    @property
    @memoized
    def phone_number_filter(self):
        value = RequiredPhoneNumberFilter.get_value(self.request, domain=None)
        if isinstance(value, str):
            return apply_leniency(value.strip())

        return None

    def _get_queryset(self):
        return PhoneNumber.objects.filter(phone_number__contains=self.phone_number_filter)

    def _get_rows(self, paginate=True, link_user=True):
        owner_cache = {}
        if self.phone_number_filter:
            data = self._get_queryset()
        else:
            return

        if paginate and self.pagination:
            data = data[self.pagination.start:self.pagination.start + self.pagination.count]

        for number in data:
            yield self._fmt_row(number, owner_cache, link_user)

    @property
    def total_records(self):
        return self._get_queryset().count()


class UserAuditReport(AdminReport, DatespanMixin):
    base_template = 'reports/base_template.html'

    slug = 'user_audit_report'
    name = ugettext_lazy("User Audit Events")

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.simple.SimpleUsername',
        'corehq.apps.reports.filters.simple.SimpleDomain',
    ]
    emailable = False
    exportable = True
    default_rows = 10

    @property
    def selected_domain(self):
        selected_domain = self.request.GET.get('domain_name', None)
        return selected_domain if selected_domain != '' else None

    @property
    def selected_user(self):
        return self.request.GET.get('username', None)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(ugettext_lazy("Date")),
            DataTablesColumn(ugettext_lazy("Username")),
            DataTablesColumn(ugettext_lazy("Domain")),
            DataTablesColumn(ugettext_lazy("IP Address")),
            DataTablesColumn(ugettext_lazy("Request Path")),
        )

    @property
    def rows(self):
        rows = []
        event_ids = navigation_event_ids_by_user(
            self.selected_user, self.datespan.startdate, self.datespan.enddate
        )
        for event_doc in iter_docs(NavigationEventAudit.get_db(), event_ids):
            event = NavigationEventAudit.wrap(event_doc)
            if not self.selected_domain or self.selected_domain == event.domain:
                rows.append([
                    event.event_date, event.user, event.domain or '', event.ip_address, event.request_path
                ])
        return rows


class UserListReport(GetParamsMixin, AdminReport):
    base_template = 'reports/base_template.html'

    slug = 'user_list_report'
    name = ugettext_lazy("User List")

    fields = [
        'corehq.apps.reports.filters.simple.SimpleSearch',
    ]
    emailable = False
    exportable = False
    ajax_pagination = True
    default_rows = 10

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Project Spaces")),
            DataTablesColumn(_("Date Joined")),
            DataTablesColumn(_("Last Login")),
            DataTablesColumn(_("Type")),
            DataTablesColumn(_("SuperUser?")),
        )

    @property
    def rows(self):
        for user in self._get_page(self._users_query()):
            yield [
                self._user_link(user['username']),
                self._get_domains(user),
                self._format_date(user['date_joined']),
                self._format_date(user['last_login']),
                user['doc_type'],
                user['is_superuser'],
            ]

    def _users_query(self):
        query = (user_es.UserES()
                 .remove_default_filters()
                 .OR(user_es.web_users(), user_es.mobile_users()))
        if 'search_string' in self.request.GET:
            search_string = self.request.GET['search_string']
            fields = ['username', 'first_name', 'last_name', 'phone_numbers',
                      'domain_membership.domain', 'domain_memberships.domain']
            query = query.search_string_query(search_string, fields)
        return query

    def _get_page(self, query):
        return (query
                .start(self.pagination.start)
                .size(self.pagination.count)
                .run().hits)

    @property
    def total_records(self):
        return self._users_query().count()

    def _user_link(self, username):
        return f'<a href="{self._user_lookup_url}?q={username}">{username}</a>'

    @cached_property
    def _user_lookup_url(self):
        return reverse('web_user_lookup')

    def _get_domains(self, user):
        if user['doc_type'] == "WebUser":
            return ", ".join(dm['domain'] for dm in user['domain_memberships'])
        return user['domain_membership']['domain']

    @staticmethod
    def _format_date(date):
        if date:
            return parse(date).strftime(SERVER_DATETIME_FORMAT)
        return "---"
