from corehq.apps.accounting.dispatcher import (
    AccountingAdminInterfaceDispatcher
)
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
from corehq.apps.smsbillables.filters import (
    DateSentFilter,
    DomainFilter,
    ShowBillablesFilter,
)
from corehq.apps.smsbillables.models import SmsBillable


class SMSBillablesInterface(GenericTabularReport):
    base_template = "accounting/report_filter_actions.html"
    section_name = "Accounting"
    dispatcher = AccountingAdminInterfaceDispatcher
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
                ((sms_billable.gateway_fee.amount
                  * sms_billable.gateway_fee_conversion_rate)
                 if (sms_billable.gateway_fee is not None
                     and sms_billable.gateway_fee_conversion_rate is not None)
                 else (sms_billable.gateway_fee.amount
                       if sms_billable.gateway_fee is not None else "")),
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
