from collections import defaultdict
from datetime import datetime, time, timedelta

from dateutil.parser import parse
from dimagi.utils.logging import notify_exception
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.db.models import Q
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop
from memoized import memoized

from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription
from corehq.apps.auditcare.utils.export import (
    all_audit_events_by_user,
    build_ip_filter,
    build_url_exclude_filter,
    build_url_include_filter,
    get_generic_log_event_row,
)
from corehq.apps.es.aggregations import TermsAggregation
from corehq.apps.es.case_search import CaseSearchES
from corehq.apps.es.cases import CaseES
from corehq.apps.es.exceptions import ESError
from corehq.apps.es.forms import FormES
from corehq.apps.hqadmin.models import HqDeploy
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.filters.select import FeatureFilter
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin
from corehq.apps.reports.standard.sms import PhoneNumberReport
from corehq.apps.sms.filters import RequiredPhoneNumberFilter
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.models import PhoneNumber
from corehq.apps.toggle_ui.models import ToggleAudit
from corehq.apps.users.dbaccessors import get_all_user_search_query
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.feature_previews import find_preview_by_slug
from corehq.motech.repeaters.const import UCRRestrictionFFStatus
from corehq.toggles import (
    NAMESPACE_DOMAIN,
    RESTRICT_DATA_SOURCE_REBUILD,
    USER_CONFIGURABLE_REPORTS,
)


def truncate_rows_to_minute_boundary(rows, max_records):
    """Truncate a sorted row list to a clean minute boundary.

    Rows must be sorted by date ascending (index 0 is the formatted date string).

    Returns:
        (truncated_rows, cutoff_datetime) tuple.
        - If no truncation needed: (rows, None)
        - If truncated to a minute boundary: (trimmed_rows, cutoff_datetime)
          where cutoff_datetime is the minute floored datetime used as the boundary
          (rows with event_date < cutoff_datetime are kept)
        - If all rows fall in the same minute (can't trim meaningfully):
          (rows[:max_records], None) — caller should show a same-minute warning
    """
    if len(rows) <= max_records:
        return rows, None

    def parse_date(date_str):
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f UTC")

    def floor_to_minute(dt):
        return dt.replace(second=0, microsecond=0)

    # Find the minute of the row that pushed us over the limit
    overflow_date = parse_date(rows[max_records][0])
    overflow_minute = floor_to_minute(overflow_date)

    # Find the minute of the first row
    first_minute = floor_to_minute(parse_date(rows[0][0]))

    # If all rows are in the same minute, we can't trim
    if overflow_minute == first_minute:
        return rows[:max_records], None

    # Trim to rows with event_date < overflow_minute
    cutoff = overflow_minute
    trimmed = [r for r in rows if parse_date(r[0]) < cutoff]

    # Guard: if trimmed still exceeds (shouldn't normally happen)
    if len(trimmed) > max_records:
        return truncate_rows_to_minute_boundary(trimmed, max_records)

    return trimmed, cutoff


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
    """Admin report for querying auditcare access logs.

    Displays NavigationEventAudit and AccessAudit records with filters
    for date range, time, username, domain, action (HTTP method or
    login/logout), IP address, URL path, and HTTP status code.

    Results are capped at MAX_RECORDS. When the query exceeds this limit
    the report trims results in memory to a clean minute boundary (so
    that the displayed rows exactly match what a narrower time filter
    would have returned), updates the end date/time filter to match,
    and shows a message explaining the adjustment. See
    ``truncate_rows_to_minute_boundary`` and ``corehq/apps/auditcare/README.md``
    for details.
    """
    slug = 'user_audit_report'
    name = gettext_lazy("User Audit Events")
    report_template_path = "hqadmin/user_audit_report.html"

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.simple.SimpleStartTime',
        'corehq.apps.reports.filters.simple.SimpleEndTime',
        'corehq.apps.reports.filters.simple.SimpleUsername',
        'corehq.apps.reports.filters.simple.SimpleOptionalDomain',
        'corehq.apps.reports.filters.select.UserAuditActionFilter',
        'corehq.apps.reports.filters.simple.IPAddressFilter',
        'corehq.apps.reports.filters.simple.URLIncludeFilter',
        'corehq.apps.reports.filters.simple.URLExcludeFilter',
        'corehq.apps.reports.filters.simple.StatusCodeFilter',
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
    def selected_action(self):
        return self.request.GET.get('action', None)

    @property
    def selected_ip_addresses(self):
        from corehq.apps.reports.filters.simple import IPAddressFilter
        raw = self.request.GET.get('ip_address', '')
        return IPAddressFilter.parse_ip_input(raw)

    @property
    def selected_url_include_patterns(self):
        raw = self.request.GET.get('url_include', '')
        return [line.strip() for line in raw.splitlines() if line.strip()]

    @property
    def selected_url_include_mode(self):
        mode = self.request.GET.get('url_include_mode', 'contains')
        return mode if mode in ('contains', 'startswith') else 'contains'

    @property
    def selected_url_exclude_patterns(self):
        raw = self.request.GET.get('url_exclude', '')
        return [line.strip() for line in raw.splitlines() if line.strip()]

    @property
    def selected_url_exclude_mode(self):
        mode = self.request.GET.get('url_exclude_mode', 'contains')
        return mode if mode in ('contains', 'startswith') else 'contains'

    @property
    def selected_status_codes(self):
        from corehq.apps.reports.filters.simple import StatusCodeFilter
        raw = self.request.GET.get('status_code', '')
        return StatusCodeFilter.parse_status_codes(raw)

    @property
    def start_time(self):
        """Get start time from request, defaulting to 00:00."""
        time_str = self.request.GET.get('start_time', '00:00')
        return self._parse_time(time_str, default=time(0, 0))

    @property
    def end_time(self):
        """Get end time from request, defaulting to 00:00 (midnight).

        Midnight signals to get_date_range_where that the full day
        should be included.
        """
        time_str = self.request.GET.get('end_time', '00:00')
        return self._parse_time(time_str, default=time(0, 0))

    def _parse_time(self, time_str, default):
        """Parse a time string in HH:MM format, returning default if invalid."""
        if not time_str:
            return default
        try:
            parts = time_str.split(':')
            if len(parts) != 2:
                return default
            return time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            return default

    @property
    def start_datetime(self):
        """Combine start date with start time to create datetime."""
        if self.datespan.startdate:
            return datetime.combine(self.datespan.startdate, self.start_time)
        return None

    @property
    def end_datetime(self):
        """Combine end date with end time to create datetime."""
        if self.datespan.enddate:
            return datetime.combine(self.datespan.enddate, self.end_time)
        return None

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(gettext_lazy("Date")),
            DataTablesColumn(gettext_lazy("Doc Type")),
            DataTablesColumn(gettext_lazy("Username")),
            DataTablesColumn(gettext_lazy("Domain")),
            DataTablesColumn(gettext_lazy("IP Address")),
            DataTablesColumn(gettext_lazy("Action")),
            DataTablesColumn(gettext_lazy("URL")),
            DataTablesColumn(gettext_lazy("Status Code")),
            DataTablesColumn(gettext_lazy("Description")),
        )

    MAX_RECORDS = 5000

    @property
    @memoized
    def rows(self):
        if not (self.selected_domain or self.selected_user):
            return []
        if self.selected_ip_addresses is None or self.selected_status_codes is None:
            return []

        nav_filters = self._build_nav_filters()
        access_filters = self._build_access_filters()
        skip_access = access_filters is False

        rows = []
        events = all_audit_events_by_user(
            self.selected_user, self.selected_domain, self.start_datetime, self.end_datetime,
            self.selected_action,
            nav_extra_filters=nav_filters,
            access_extra_filters=None if skip_access else access_filters,
            skip_access=skip_access,
        )
        count = 0
        for event in events:
            row = get_generic_log_event_row(event)
            rows.append(row)
            count += 1
            if count > self.MAX_RECORDS:
                break

        truncated_rows, cutoff_dt = truncate_rows_to_minute_boundary(rows, self.MAX_RECORDS)
        self._truncation_cutoff = cutoff_dt
        self._truncation_same_minute = (len(rows) > self.MAX_RECORDS and cutoff_dt is None)
        return truncated_rows

    def _build_common_filters(self):
        filters = Q()

        ip_parsed = self.selected_ip_addresses
        if ip_parsed:
            ip_q = build_ip_filter(ip_parsed)
            if ip_q:
                filters &= ip_q

        url_include = build_url_include_filter(
            self.selected_url_include_patterns, self.selected_url_include_mode
        )
        if url_include:
            filters &= url_include

        url_exclude = build_url_exclude_filter(
            self.selected_url_exclude_patterns, self.selected_url_exclude_mode
        )
        if url_exclude:
            filters &= url_exclude

        return filters if filters != Q() else None

    def _build_nav_filters(self):
        filters = self._build_common_filters() or Q()
        status_codes = self.selected_status_codes
        if status_codes:
            filters &= Q(status_code__in=status_codes)
        return filters if filters != Q() else None

    def _build_access_filters(self):
        status_codes = self.selected_status_codes
        if status_codes:
            return False  # AccessAudit has no status code
        return self._build_common_filters()

    def _is_invalid_time_range(self):
        """Check if start date equals end date and end time is before start time.

        Midnight (00:00) as end time is a special value meaning "include
        the full day", so it is always valid.
        """
        if (
            self.datespan.startdate and self.datespan.enddate
            and self.datespan.startdate == self.datespan.enddate
        ):
            if self.end_time == time(0, 0):
                return False
            return self.end_time < self.start_time
        return False

    @property
    def report_context(self):
        context = super().report_context

        if not (self.selected_domain or self.selected_user):
            context['warning_message'] = _("You must specify either a username or a domain. "
                    "Requesting all audit events across all users and domains would exceed system limits.")
        elif self._is_invalid_time_range():
            context['warning_message'] = _("The end time cannot be earlier than the start time when "
                    "both dates are the same. Please adjust your time range.")
        elif self.selected_ip_addresses is None:
            context['warning_message'] = _(
                "Invalid IP address filter. Use single IPs, CIDR notation "
                "(/8, /16, /24, /32), or comma-separated combinations."
            )
        elif self.selected_status_codes is None:
            context['warning_message'] = _(
                "Invalid status code filter. Use comma-separated integers (e.g. 200, 403, 500)."
            )

        # URL domain hint
        if (self.selected_url_include_mode == 'startswith'
                and self.selected_domain
                and self.selected_url_include_patterns):
            domain_prefix = f'/a/{self.selected_domain}/'
            if not any(p.startswith(domain_prefix) for p in self.selected_url_include_patterns):
                context.setdefault('info_message', '')
                context['info_message'] += _(
                    'Note: URLs for this domain typically start with "{domain_prefix}".'
                ).format(domain_prefix=domain_prefix)

        # Truncation messages (set by rows property)
        # Access rows to trigger the query and truncation logic
        _rows = self.rows  # noqa: F841
        if getattr(self, '_truncation_same_minute', False):
            context['truncation_message'] = _(
                "Showing {max_records} results, but there are additional events within the "
                "same minute that are not shown. Try narrowing by username, domain, IP address, "
                "or other filters to see all results."
            ).format(max_records=self.MAX_RECORDS)
            context['truncation_level'] = 'warning'
        elif getattr(self, '_truncation_cutoff', None):
            cutoff = self._truncation_cutoff
            context['truncation_message'] = _(
                "Showing events through {cutoff_time}. Your query returned more than "
                "{max_records} results; the end date/time has been adjusted. "
                "To see later events, set the start time to {cutoff_time}."
            ).format(
                cutoff_time=cutoff.strftime("%Y-%m-%d %H:%M UTC"),
                max_records=self.MAX_RECORDS,
            )
            context['truncation_level'] = 'info'
            context['adjusted_end_date'] = cutoff.strftime("%Y-%m-%d")
            context['adjusted_end_time'] = cutoff.strftime("%H:%M")

        return context


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
            .exclude(plan_version__plan__edition=SoftwarePlanEdition.FREE)
            .filter(is_active=True)
            .values_list('subscriber__domain', flat=True)
        ))


class FeaturePreviewStatusReport(AdminReport):
    slug = 'feature_preview_status_report'
    name = gettext_lazy("Feature Preview Status Report")

    fields = [
        'corehq.apps.reports.filters.select.FeatureFilter',
    ]
    emailable = False
    exportable = True

    def selected_feature(self):
        return self.get_request_param(FeatureFilter.slug, None, from_json=True)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(gettext_lazy("Domain")),
            DataTablesColumn(gettext_lazy("Enabled By")),
            DataTablesColumn(gettext_lazy("Enabled At")),
        )

    @property
    def rows(self):
        if not self.selected_feature():
            return []
        feature = find_preview_by_slug(self.selected_feature())
        if not feature:
            return []
        rows = []
        domains = feature.get_enabled_domains()
        records = (
            ToggleAudit.objects
            .filter(slug=feature.slug, namespace=NAMESPACE_DOMAIN, item__in=domains)
            .order_by('item', 'created')
            .distinct('item')
        )

        for record in records:
            rows.append([
                record.item,
                record.username,
                record.created,
            ])

        domains_with_records = {record.item for record in records}
        domains_without_records = set(domains) - domains_with_records

        for domain in domains_without_records:
            rows.append([
                domain,
                _("Not recorded"),
                _("Not recorded"),
            ])

        return rows


class FeaturePreviewAuditReport(AdminReport):
    slug = 'feature_preview_audit_report'
    name = gettext_lazy("Feature Preview Audit Report")

    fields = [
        'corehq.apps.reports.filters.simple.SimpleDomain',
        'corehq.apps.reports.filters.select.FeatureFilter',
    ]
    emailable = False
    exportable = True

    @property
    def selected_domain(self):
        selected_domain = self.request.GET.get('domain_name', None)
        return selected_domain or None

    def selected_feature(self):
        return self.get_request_param(FeatureFilter.slug, None, from_json=True)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(gettext_lazy("Feature")),
            DataTablesColumn(gettext_lazy("Action")),
            DataTablesColumn(gettext_lazy("Changed By")),
            DataTablesColumn(gettext_lazy("Changed At")),
        )

    @property
    def rows(self):
        if not self.selected_domain:
            return []

        base_filter = {
            'namespace': NAMESPACE_DOMAIN,
            'item': self.selected_domain
        }

        if self.selected_feature():
            feature = find_preview_by_slug(self.selected_feature())
            if not feature:
                return []
            base_filter['slug'] = feature.slug
        else:
            from corehq.feature_previews import all_previews
            all_slugs = [preview.slug for preview in all_previews()]
            base_filter['slug__in'] = all_slugs

        rows = []
        records = ToggleAudit.objects.filter(**base_filter)

        for record in records:
            action = _("Enabled")
            if record.action == ToggleAudit.ACTION_REMOVE:
                action = _("Disabled")
            elif record.action == ToggleAudit.ACTION_UPDATE_RANDOMNESS:
                action = _("Update Randomness")
            rows.append([
                find_preview_by_slug(record.slug).label,
                action,
                record.username,
                record.created,
            ])

        return rows
