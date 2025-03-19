from collections import defaultdict
from datetime import datetime, timedelta

from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from django.contrib.humanize.templatetags.humanize import naturaltime

from dateutil.parser import parse
from memoized import memoized

from dimagi.utils.logging import notify_exception

from corehq.apps.accounting.models import Subscription, SoftwarePlanEdition
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
from corehq.apps.es.cases import CaseES
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es.forms import FormES
from corehq.toggles import USER_CONFIGURABLE_REPORTS, RESTRICT_DATA_SOURCE_REBUILD
from corehq.motech.repeaters.const import UCRRestrictionFFStatus
from corehq.apps.es.aggregations import TermsAggregation
from corehq.apps.es.exceptions import ESError


class AdminReport(GenericTabularReport):
    dispatcher = AdminReportDispatcher
    base_template = 'reports/bootstrap3/base_template.html'
    report_template_path = "reports/bootstrap3/tabular.html"
    section_name = gettext_noop("ADMINREPORT")
    default_params = {}
    is_admin_report = True


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
    base_template = 'reports/bootstrap3/base_template.html'

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
    base_template = 'reports/bootstrap3/base_template.html'

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


class UCRRebuildRestrictionTable:
    UCR_RESTRICTION_THRESHOLD = 1_000_000

    restriction_ff_status: str

    def __init__(self, *args, **kwargs):
        self.restriction_ff_status = kwargs.get('restriction_ff_status')

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(gettext_lazy("Domain")),
            DataTablesColumn(gettext_lazy("Case count")),
            DataTablesColumn(gettext_lazy("Form count")),
            DataTablesColumn(gettext_lazy("UCR rebuild restriction status")),
        )

    @property
    def rows(self):
        rows = []

        ucr_domains = self.ucr_domains
        if not ucr_domains:
            return []

        case_count_by_domain = self._case_count_by_domain(ucr_domains)
        form_count_by_domain = self._forms_count_by_domain(ucr_domains)

        for domain in ucr_domains:
            case_count = getattr(case_count_by_domain.get(domain), 'doc_count', 0)
            form_count = getattr(form_count_by_domain.get(domain), 'doc_count', 0)

            if self.should_show_domain(domain, case_count, form_count):
                rows.append(
                    self._row_data(domain, case_count, form_count)
                )

        return rows

    @property
    @memoized
    def ucr_domains(self):
        return USER_CONFIGURABLE_REPORTS.get_enabled_domains()

    def should_show_domain(self, domain, total_cases, total_forms):
        if self._show_all_domains:
            return True

        should_restrict_rebuild = self._should_restrict_rebuild(total_cases, total_forms)
        restriction_ff_enabled = self._rebuild_restricted_ff_enabled(domain)

        if self._show_ff_enabled_domains:
            return restriction_ff_enabled
        if self._show_ff_disabled_domains:
            return not restriction_ff_enabled
        if self._show_should_enable_ff_domains:
            return should_restrict_rebuild and not restriction_ff_enabled
        if self._show_should_disable_ff_domains:
            return not should_restrict_rebuild and restriction_ff_enabled

    @staticmethod
    def _case_count_by_domain(domains):
        return CaseES().domain(domains).size(0).aggregation(
            TermsAggregation('domain', 'domain.exact')
        ).run().aggregations.domain.buckets_dict

    @staticmethod
    def _forms_count_by_domain(domains):
        return FormES().domain(domains).size(0).aggregation(
            TermsAggregation('domain', 'domain.exact')
        ).run().aggregations.domain.buckets_dict

    def _row_data(self, domain, case_count, form_count):
        return [
            domain,
            case_count,
            form_count,
            self._ucr_rebuild_restriction_status_column_data(domain, case_count, form_count),
        ]

    def _should_restrict_rebuild(self, case_count, form_count):
        return case_count >= self.UCR_RESTRICTION_THRESHOLD or form_count >= self.UCR_RESTRICTION_THRESHOLD

    @staticmethod
    @memoized
    def _rebuild_restricted_ff_enabled(domain):
        return RESTRICT_DATA_SOURCE_REBUILD.enabled(domain)

    @property
    def _show_ff_enabled_domains(self):
        return self.restriction_ff_status == UCRRestrictionFFStatus.Enabled.name

    @property
    def _show_ff_disabled_domains(self):
        return self.restriction_ff_status == UCRRestrictionFFStatus.NotEnabled.name

    @property
    def _show_should_enable_ff_domains(self):
        return self.restriction_ff_status == UCRRestrictionFFStatus.ShouldEnable.name

    @property
    def _show_should_disable_ff_domains(self):
        return self.restriction_ff_status == UCRRestrictionFFStatus.CanDisable.name

    @property
    def _show_all_domains(self):
        return not self.restriction_ff_status

    def _ucr_rebuild_restriction_status_column_data(self, domain, case_count, form_count):
        from django.utils.safestring import mark_safe
        from corehq.apps.toggle_ui.views import ToggleEditView

        restriction_ff_enabled = self._rebuild_restricted_ff_enabled(domain)
        toggle_edit_url = reverse(ToggleEditView.urlname, args=(RESTRICT_DATA_SOURCE_REBUILD.slug,))

        if self._should_restrict_rebuild(case_count, form_count):
            if not restriction_ff_enabled:
                return mark_safe(f"""
                    <a href={toggle_edit_url}>{gettext_lazy("Rebuild restriction required")}</a>
                """)
            return gettext_lazy("Rebuild restricted")

        if restriction_ff_enabled:
            return mark_safe(f"""
                <a href={toggle_edit_url}>{gettext_lazy("Rebuild restriction not required")}</a>
            """)
        return gettext_lazy("No rebuild restriction required")


class UCRDataLoadReport(AdminReport):
    slug = 'ucr_data_load'
    name = gettext_lazy("UCR Domains Data Report")

    fields = [
        'corehq.apps.reports.filters.select.UCRRebuildStatusFilter',
    ]
    emailable = False
    exportable = False
    disable_pagination = True
    ajax_pagination = False
    use_datatables = False

    def __init__(self, request, *args, **kwargs):
        self.table_data = UCRRebuildRestrictionTable(
            restriction_ff_status=request.GET.get('ucr_rebuild_restriction')
        )
        super().__init__(request, *args, **kwargs)

    @property
    def headers(self):
        return self.table_data.headers

    @property
    def rows(self):
        return self.table_data.rows


class StaleCasesTable:
    STOP_POINT_DAYS_AGO = 365 * 20
    AGG_DATE_RANGE = 150
    STALE_DATE_THRESHOLD_DAYS = 365

    BACKOFF_AMOUNT_DAYS = 30
    MAX_BACKOFF_COUNT = 2

    def __init__(self):
        self._rows = None
        self.stop_date = datetime.now() - timedelta(days=self.STOP_POINT_DAYS_AGO)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(gettext_lazy("Domain")),
            DataTablesColumn(gettext_lazy("Case count"))
        )

    @property
    def rows(self):
        if self._rows is None:
            self._rows = []
            case_count_by_domain = self._aggregate_case_count_data()
            for domain, case_count in case_count_by_domain.items():
                self._rows.append([domain, case_count])
        return self._rows

    def _aggregate_case_count_data(self):
        end_date = datetime.now() - timedelta(days=self.STALE_DATE_THRESHOLD_DAYS)
        agg_res = defaultdict(lambda: 0)
        curr_backoff_count = 0
        curr_agg_date_range = self.AGG_DATE_RANGE
        domains = self._get_domains()
        while (True):
            start_date = end_date - timedelta(days=curr_agg_date_range)
            try:
                query_res = self._stale_case_count_in_date_range(domains, start_date, end_date)
            except ESError as e:
                curr_backoff_count += 1
                if curr_backoff_count <= self.MAX_BACKOFF_COUNT:
                    curr_agg_date_range -= self.BACKOFF_AMOUNT_DAYS
                else:
                    notify_exception(
                        None,
                        'ES query timed out while compiling stale case report email.',
                        details={
                            'error': str(e),
                            'start_date': start_date.strftime("%Y-%m-%d"),
                            'end_date': end_date.strftime("%Y-%m-%d")
                        }
                    )
                    raise ESError()
            else:
                curr_backoff_count = 0
                curr_agg_date_range = self.AGG_DATE_RANGE
                self._merge_agg_data(agg_res, query_res)
                end_date = start_date
                if end_date <= self.stop_date:
                    break
        return agg_res

    def _merge_agg_data(self, agg_res, query_res):
        for domain, case_count in query_res.items():
            agg_res[domain] += case_count

    def _stale_case_count_in_date_range(self, domains, start_date, end_date):
        return (
            CaseSearchES()
            .domain(domains)
            .modified_range(gt=start_date, lt=end_date)
            .is_closed(False)
            .aggregation(
                TermsAggregation('domain', 'domain.exact')
            )
            .size(0)
        ).run().aggregations.domain.counts_by_bucket()

    def _get_domains(self):
        return list(set(
            Subscription.visible_objects
            .exclude(plan_version__plan__edition=SoftwarePlanEdition.COMMUNITY)
            .filter(is_active=True)
            .values_list('subscriber__domain', flat=True)
        ))
