from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.contrib.humanize.templatetags.humanize import naturaltime

from dateutil.parser import parse
from memoized import memoized

from phonelog.models import DeviceReportEntry
from phonelog.reports import BaseDeviceLogReport

from corehq.apps.auditcare.utils.export import navigation_events_by_user
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin
from corehq.apps.reports.standard.sms import PhoneNumberReport
from corehq.apps.sms.filters import RequiredPhoneNumberFilter
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.models import PhoneNumber
from corehq.apps.users.dbaccessors import get_all_user_search_query
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.apps.hqadmin.models import HqDeploy


class AdminReport(GenericTabularReport):
    dispatcher = AdminReportDispatcher
    base_template = 'reports/base_template.html'
    report_template_path = "reports/bootstrap3/tabular.html"
    section_name = gettext_noop("ADMINREPORT")
    default_params = {}
    is_admin_report = True


class DeviceLogSoftAssertReport(BaseDeviceLogReport, AdminReport):
    slug = 'device_log_soft_asserts'
    name = gettext_lazy("Global Device Logs Soft Asserts")

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.devicelog.DeviceLogDomainFilter',
        'corehq.apps.reports.filters.devicelog.DeviceLogCommCareVersionFilter',
    ]
    emailable = False
    default_rows = 10

    _username_fmt = "{username}"
    _device_users_fmt = "{username}"
    _device_id_fmt = "{device}"
    _log_tag_fmt = "<label class='{classes}'>{text}</label>"

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
            range=slice(self.pagination.start,
                        self.pagination.start + self.pagination.count)
        )
        return rows

    def _filter_logs(self):
        logs = DeviceReportEntry.objects.filter(
            date__range=[self.datespan.startdate_param_utc,
                         self.datespan.enddate_param_utc]
        ).filter(type='soft-assert')

        if self.selected_domain is not None:
            logs = logs.filter(domain__exact=self.selected_domain)

        if self.selected_commcare_version is not None:
            logs = logs.filter(app_version__contains='"{}"'.format(
                self.selected_commcare_version))

        return logs

    def _create_row(self, log, *args, **kwargs):
        row = super(DeviceLogSoftAssertReport, self)._create_row(
            log, *args, **kwargs)
        row.append(log.domain)
        return row


class AdminPhoneNumberReport(PhoneNumberReport):
    name = gettext_lazy("Admin Phone Number Report")
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
            data = data[
                self.pagination.start:self.pagination.start + self.pagination.count]

        for number in data:
            yield self._fmt_row(number, owner_cache, link_user)

    @property
    def total_records(self):
        return self._get_queryset().count()


class UserAuditReport(AdminReport, DatespanMixin):
    slug = 'user_audit_report'
    name = gettext_lazy("User Audit Events")

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
            DataTablesColumn(gettext_lazy("Date")),
            DataTablesColumn(gettext_lazy("Username")),
            DataTablesColumn(gettext_lazy("Domain")),
            DataTablesColumn(gettext_lazy("IP Address")),
            DataTablesColumn(gettext_lazy("Request Method")),
            DataTablesColumn(gettext_lazy("Request Path")),
        )

    @property
    def rows(self):
        rows = []
        events = navigation_events_by_user(
            self.selected_user, self.datespan.startdate, self.datespan.enddate
        )
        for event in events:
            if not self.selected_domain or self.selected_domain == event.domain:
                rows.append([
                    event.event_date,
                    event.user,
                    event.domain or '',
                    event.ip_address,
                    event.request_method,
                    event.request_path
                ])
        return rows


class UserListReport(GetParamsMixin, AdminReport):
    base_template = 'reports/base_template.html'

    slug = 'user_list_report'
    name = gettext_lazy("User List")

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
        search_string = self.request.GET.get('search_string', None)
        return get_all_user_search_query(search_string)

    def _get_page(self, query):
        return (query
                .start(self.pagination.start)
                .size(self.pagination.count)
                .run().hits)

    @property
    def total_records(self):
        return self._users_query().count()

    def _user_link(self, username):
        return format_html(
            '<a href="{url}?q={username}">{username}</a>',
            url=self._user_lookup_url,
            username=username
        )

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


class DeployHistoryReport(GetParamsMixin, AdminReport):
    base_template = 'reports/base_template.html'

    slug = 'deploy_history_report'
    name = gettext_lazy("Deploy History Report")

    emailable = False
    exportable = False
    ajax_pagination = True
    default_rows = 10

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Date"), sortable=False),
            DataTablesColumn(_("User"), sortable=False),
            DataTablesColumn(_("Diff URL"), sortable=False),
            DataTablesColumn(_("Commit"), sortable=False),
        )

    @property
    def rows(self):
        deploy_list = HqDeploy.objects.all()
        start = self.pagination.start
        end = self.pagination.start + self.pagination.count
        for deploy in deploy_list[start:end]:
            yield [
                self._format_date(deploy.date),
                deploy.user,
                self._hyperlink_diff_url(deploy.diff_url),
                self._shorten_and_hyperlink_commit(deploy.commit),
            ]

    @property
    def total_records(self):
        return HqDeploy.objects.count()

    def _format_date(self, date):
        if date:
            return format_html(
                '<div>{}</div><div>{}</div>',
                naturaltime(date),
                date.strftime(SERVER_DATETIME_FORMAT)
            )
        return "---"

    def _hyperlink_diff_url(self, diff_url):
        return format_html('<a href="{}">Diff with previous</a>', diff_url)

    def _shorten_and_hyperlink_commit(self, commit_sha):
        if commit_sha:
            return format_html(
                '<a href="https://github.com/dimagi/commcare-hq/commit/{full_sha}">{abbrev_sha}</a>',
                full_sha=commit_sha,
                abbrev_sha=commit_sha[:7]
            )
        return None
