from django.db.models.aggregates import Count
from corehq.apps.accounting.filters import DateCreatedFilter
from corehq.apps.reports.datatables import (
    DataTablesColumn,
    DataTablesHeader,
)
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.sms.models import (
    INCOMING,
    OUTGOING,
)
from corehq.apps.smsbillables.dispatcher import SMSAdminInterfaceDispatcher
from corehq.apps.smsbillables.filters import (
    CountryCodeFilter,
    DateSentFilter,
    DirectionFilter,
    DomainFilter,
    GatewayTypeFilter,
    ShowBillablesFilter,
    SpecificGateway,
)
from corehq.apps.smsbillables.models import (
    SmsBillable,
    SmsGatewayFee,
    SmsGatewayFeeCriteria,
)
from couchexport.models import Format


class SMSBillablesInterface(GenericTabularReport):
    base_template = "accounting/report_filter_actions.html"
    section_name = "Accounting"
    dispatcher = SMSAdminInterfaceDispatcher
    name = "SMS Billables"
    description = "List of all SMS Billables"
    slug = "sms_billables"
    ajax_pagination = True
    exportable = True
    exportable_all = True
    export_format_override = Format.UNZIPPED_CSV
    fields = [
        'corehq.apps.smsbillables.interface.DateSentFilter',
        'corehq.apps.accounting.interface.DateCreatedFilter',
        'corehq.apps.smsbillables.interface.ShowBillablesFilter',
        'corehq.apps.smsbillables.interface.DomainFilter',
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Date of Message"),
            DataTablesColumn("Project Space"),
            DataTablesColumn("Direction"),
            DataTablesColumn("Gateway Fee", sortable=False),
            DataTablesColumn("Usage Fee", sortable=False),
            DataTablesColumn("Message Log ID", sortable=False),
            DataTablesColumn("Phone Number"),
            DataTablesColumn("Is Valid?", sortable=False),
            DataTablesColumn("Date Created"),
        )

    @property
    def sort_field(self):
        sort_fields = [
            'date_sent',
            'domain',
            'direction',
            'phone_number',
            'date_created',
        ]
        sort_index = int(self.request.GET.get('iSortCol_0', 2))
        sort_index = 1 if sort_index == 0 else sort_index - 1
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
                    'value': ShowBillablesFilter.get_value(self.request, self.domain)},
                {
                    'name': DomainFilter.slug,
                    'value': DomainFilter.get_value(self.request, self.domain)
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
        return query.aggregate(Count('id'))['id__count']

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
                ("Incoming"
                 if sms_billable.direction == INCOMING
                 else ("Outgoing"
                       if sms_billable.direction == OUTGOING
                       else "")),
                sms_billable.gateway_charge,
                (sms_billable.usage_fee.amount
                 if sms_billable.usage_fee is not None else ""),
                sms_billable.log_id,
                sms_billable.phone_number,
                sms_billable.is_valid,
                sms_billable.date_created,
            ]
            for sms_billable in sms_billables
        ]

    @property
    def sms_billables(self):
        selected_billables = SmsBillable.objects.filter(
            date_sent__gte=DateSentFilter.get_start_date(self.request),
            date_sent__lte=DateSentFilter.get_end_date(self.request),
        )
        if DateCreatedFilter.use_filter(self.request):
            selected_billables = selected_billables.filter(
                date_created__gte=DateCreatedFilter.get_start_date(
                    self.request),
                date_created__lte=DateCreatedFilter.get_end_date(self.request),
            )
        show_billables = ShowBillablesFilter.get_value(
            self.request, self.domain)
        if show_billables:
            selected_billables = selected_billables.filter(
                is_valid=(show_billables == ShowBillablesFilter.VALID),
            )
        domain = DomainFilter.get_value(self.request, self.domain)
        if domain:
            selected_billables = selected_billables.filter(
                domain=domain,
            )
        return selected_billables


class SMSGatewayFeeCriteriaInterface(GenericTabularReport):
    base_template = "accounting/report_filter_actions.html"
    section_name = "Accounting"
    dispatcher = SMSAdminInterfaceDispatcher
    name = "SMS Gateway Fee Criteria"
    description = "List of all SMS Gateway Fee Criteria"
    slug = "sms_gateway_fee_criteria"
    exportable = True
    exportable_all = True
    fields = [
        'corehq.apps.smsbillables.interface.GatewayTypeFilter',
        'corehq.apps.smsbillables.interface.SpecificGateway',
        'corehq.apps.smsbillables.interface.DirectionFilter',
        'corehq.apps.smsbillables.interface.CountryCodeFilter',
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Gateway Type"),
            DataTablesColumn("Specific Gateway"),
            DataTablesColumn("Direction"),
            DataTablesColumn("Country Code"),
            DataTablesColumn("Prefix"),
            DataTablesColumn("Fee (Amount, Currency)")
        )

    @property
    def get_all_rows(self):
        return self.rows

    @property
    def rows(self):
        rows = []
        for criteria in self.sms_gateway_fee_criteria:
            gateway_fee = SmsGatewayFee.get_by_criteria_obj(criteria)
            rows.append([
                criteria.backend_api_id,
                (criteria.backend_instance
                 if criteria.backend_instance is not None else "Any"),
                criteria.direction,
                (criteria.country_code
                 if criteria.country_code is not None else "Any"),
                criteria.prefix or "Any",
                "%(amount)s %(currency)s" % {
                    'amount': str(gateway_fee.amount),
                    'currency': gateway_fee.currency.code,
                },
            ])
        return rows

    @property
    def sms_gateway_fee_criteria(self):
        selected_criteria = SmsGatewayFeeCriteria.objects.filter()
        gateway_type = GatewayTypeFilter.get_value(self.request, self.domain)
        if gateway_type:
            selected_criteria = selected_criteria.filter(
                backend_api_id=gateway_type,
            )
        specific_gateway = SpecificGateway.get_value(self.request, self.domain)
        if specific_gateway:
            selected_criteria = selected_criteria.filter(
                backend_instance=specific_gateway,
            )
        direction = DirectionFilter.get_value(self.request, self.domain)
        if direction:
            selected_criteria = selected_criteria.filter(
                direction=direction,
            )
        country_code = CountryCodeFilter.get_value(self.request, self.domain)
        if country_code:
            selected_criteria = selected_criteria.filter(
                country_code=int(country_code),
            )
        return selected_criteria
