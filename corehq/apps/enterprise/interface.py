
from corehq.apps.sms.models import INCOMING, OUTGOING
from django.utils.translation import ugettext as _
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.enterprise.dispatcher import EnterpriseReportDispatcher
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.accounting.filters import DateCreatedFilter

from corehq.apps.smsbillables.filters import (
    DateSentFilter,
    GatewayTypeFilter,
    HasGatewayFeeFilter,
    ShowBillablesFilter,
)
from corehq.apps.enterprise.filters import EnterpriseDomainFilter
from corehq.apps.accounting.models import (
    BillingAccount,
    Subscription
)
from corehq.apps.smsbillables.models import (
    SmsBillable,
)

from couchexport.models import Format
from dimagi.utils.dates import DateSpan


class EnterpriseSMSBillablesReport(GenericTabularReport):
    base_template = "accounting/report_filter_actions.html"
    section_name = _("Enterprise")
    dispatcher = EnterpriseReportDispatcher
    name = _("SMS Detailed Report")
    description = _("This is a report of SMS details that can be altered by using the filter options \
    above. Once you are happy with your filters, simply click Apply.")
    slug = "Enterprise"
    ajax_pagination = True
    exportable = True
    exportable_all = True
    export_format_override = Format.UNZIPPED_CSV
    fields = [
        DateSentFilter,
        DateCreatedFilter,
        ShowBillablesFilter,
        EnterpriseDomainFilter,
        HasGatewayFeeFilter,
        GatewayTypeFilter,
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Date of Message")),
            DataTablesColumn(_("Project Space")),
            DataTablesColumn(_("Direction")),
            DataTablesColumn(_("SMS parts")),
            DataTablesColumn(_("Gateway"), sortable=False),
            DataTablesColumn(_("Gateway Charge"), sortable=False),
            DataTablesColumn(_("Usage Charge"), sortable=False),
            DataTablesColumn(_("Total Charge"), sortable=False),
            DataTablesColumn(_("Message Log ID"), sortable=False),
            DataTablesColumn(_("Is Valid?"), sortable=False),
            DataTablesColumn(_("Date Created")),
        )

    @property
    def sort_field(self):
        sort_fields = [
            'date_sent',
            'domain',
            'direction',
            'multipart_count',
            None,
            None,
            None,
            None,
            None,
            None,
            'date_created',
        ]
        sort_index = int(self.request.GET.get('iSortCol_0', 0))
        field = sort_fields[sort_index]
        sort_descending = self.request.GET.get('sSortDir_0', 'asc') == 'desc'
        return field if not sort_descending else '-{0}'.format(field)

    @property
    def shared_pagination_GET_params(self):
        return DateSentFilter.shared_pagination_GET_params(self.request) + \
            DateCreatedFilter.shared_pagination_GET_params(self.request) + [
                {
                    'name': DateCreatedFilter.optional_filter_slug(),
                    'value': DateCreatedFilter.optional_filter_string_value(self.request)
                },
                {
                    'name': ShowBillablesFilter.slug,
                    'value': ShowBillablesFilter.get_value(self.request, self.domain)
                },
                {
                    'name': EnterpriseDomainFilter.slug,
                    'value': EnterpriseDomainFilter.get_value(self.request, self.domain)
                },
                {
                    'name': HasGatewayFeeFilter.slug,
                    'value': HasGatewayFeeFilter.get_value(self.request, self.domain)
                },
                {
                    'name': GatewayTypeFilter.slug,
                    'value': GatewayTypeFilter.get_value(self.request, self.domain)
                },
        ]

    @property
    def get_all_rows(self):
        query = self.sms_billables
        query = query.order_by(self.sort_field)
        return self._format_billables(query)

    @property
    def total_records(self):
        query = self.sms_billables
        return query.count()

    @property
    def rows(self):
        query = self.sms_billables
        query = query.order_by(self.sort_field)

        sms_billables = query[self.pagination.start:(self.pagination.start + self.pagination.count)]
        return self._format_billables(sms_billables)

    def _format_billables(self, sms_billables):
        return [
            [
                sms_billable.date_sent,
                sms_billable.domain,
                {
                    INCOMING: _("Incoming"),
                    OUTGOING: _("Outgoing"),
                }[sms_billable.direction],
                sms_billable.multipart_count,
                sms_billable.gateway_fee.criteria.backend_api_id if sms_billable.gateway_fee else "",
                sms_billable.gateway_charge,
                sms_billable.usage_charge,
                sms_billable.gateway_charge + sms_billable.usage_charge,
                sms_billable.log_id,
                sms_billable.is_valid,
                sms_billable.date_created,
            ]
            for sms_billable in sms_billables
        ]

    @property
    def sms_billables(self):
        datespan = DateSpan(DateSentFilter.get_start_date(self.request), DateSentFilter.get_end_date(self.request))
        selected_billables = SmsBillable.get_billables_sent_between(datespan)
        if DateCreatedFilter.use_filter(self.request):
            date_span = DateSpan(
                DateCreatedFilter.get_start_date(self.request), DateCreatedFilter.get_end_date(self.request)
            )
            selected_billables = SmsBillable.filter_selected_billables_by_date(selected_billables, date_span)
        show_billables = ShowBillablesFilter.get_value(
            self.request, self.domain)
        if show_billables:
            selected_billables = SmsBillable.filter_selected_billables_show_billables(
                selected_billables, show_billables
            )
        domain = EnterpriseDomainFilter.get_value(self.request, self.domain)
        if domain:
            selected_billables = selected_billables.filter(
                domain=domain,
            )
        else:
            account = BillingAccount.get_account_by_domain(self.request.domain)
            domains = Subscription.get_active_domains_for_account(account)
            selected_billables = selected_billables.filter(
                domain__in=domains
            )
        has_gateway_fee = HasGatewayFeeFilter.get_value(
            self.request, self.domain
        )
        if has_gateway_fee:
            if has_gateway_fee == HasGatewayFeeFilter.YES:
                selected_billables = selected_billables.exclude(
                    gateway_fee=None
                )
            else:
                selected_billables = selected_billables.filter(
                    gateway_fee=None
                )
        gateway_type = GatewayTypeFilter.get_value(self.request, self.domain)
        if gateway_type:
            selected_billables = selected_billables.filter(
                gateway_fee__criteria__backend_api_id=gateway_type,
            )
        return selected_billables
