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
    SmsGatewayFeeCriteria,
)


class SMSBillablesInterface(GenericTabularReport):
    base_template = "accounting/report_filter_actions.html"
    section_name = "Accounting"
    dispatcher = SMSAdminInterfaceDispatcher
    name = "SMS Billables"
    description = "List of all SMS Billables"
    slug = "sms_billables"
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
            DataTablesColumn("Gateway Fee"),
            DataTablesColumn("Usage Fee"),
            DataTablesColumn("Message Log ID"),
            DataTablesColumn("Phone Number"),
            DataTablesColumn("Is Valid?"),
            DataTablesColumn("Date Created"),
        )

    @property
    def rows(self):
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
            for sms_billable in self.sms_billables
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
        )

    @property
    def rows(self):
        return [
            [
                criteria.backend_api_id,
                (criteria.backend_instance
                 if criteria.backend_instance is not None else "Any"),
                criteria.direction,
                (criteria.country_code
                 if criteria.country_code is not None else "Any"),
            ]
            for criteria in self.sms_gateway_fee_criteria
        ]

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
