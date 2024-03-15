import calendar
import datetime

from django.urls import reverse
from django.utils.translation import gettext_noop as _

from dateutil.relativedelta import relativedelta

from corehq.apps.sso.models import IdentityProviderType
from dimagi.utils.dates import DateSpan

from corehq.apps.accounting.async_handlers import (
    AccountFilterAsyncHandler,
    BillingContactInfoAsyncHandler,
    DomainFilterAsyncHandler,
    InvoiceBalanceAsyncHandler,
    InvoiceNumberAsyncHandler,
    SoftwarePlanAsyncHandler,
    SubscriberFilterAsyncHandler,
    SubscriptionFilterAsyncHandler,
    CustomerInvoiceNumberAsyncHandler,
)
from corehq.apps.accounting.models import (
    BillingAccountType,
    EntryPoint,
    ProBonoStatus,
    SoftwarePlanEdition,
    SoftwarePlanVisibility,
    SubscriptionAdjustmentMethod,
    SubscriptionType,
    CreditAdjustmentReason,
)
from corehq.apps.reports.filters.base import (
    BaseReportFilter,
    BaseSimpleFilter,
    BaseSingleOptionFilter,
)
from corehq.util.dates import iso_string_to_date


class BaseAccountingSingleOptionFilter(BaseSingleOptionFilter):
    is_paginated = True

    @property
    def pagination_source(self):
        from corehq.apps.accounting.views import AccountingSingleOptionResponseView
        return reverse(AccountingSingleOptionResponseView.urlname)


class AccountTypeFilter(BaseSingleOptionFilter):
    slug = 'account_type'
    label = _("Account Type")
    default_text = _("All")
    options = BillingAccountType.CHOICES


class NameFilter(BaseAccountingSingleOptionFilter):
    slug = 'account_name'
    label = _("Account Name")
    default_text = _("All")
    async_handler = AccountFilterAsyncHandler
    async_action = 'account_name'


class DomainFilter(BaseAccountingSingleOptionFilter):
    slug = 'domain_name'
    label = _("Project Space")
    default_text = _("All")
    async_handler = DomainFilterAsyncHandler
    async_action = 'domain_name'


class CreditAdjustmentReasonFilter(BaseSingleOptionFilter):
    slug = 'credit_adjustment_reason'
    label = _("Credit Adjustment Reason")
    default_text = _("Any Reason")
    options = CreditAdjustmentReason.CHOICES


class IdPServiceTypeFilter(BaseSingleOptionFilter):
    slug = 'idp_service_type'
    label = _("Service Type")
    default_text = _("Any Service")
    options = IdentityProviderType.CHOICES


class CreditAdjustmentLinkFilter(BaseSingleOptionFilter):
    slug = 'credit_adjustment_link'
    label = _("Credit Adjustment Reason")
    default_text = _("Linked to Any Transaction")
    options = (
        ('invoice', "Linked to Invoice"),
        ('customer_invoice', "Linked to Customer Invoice"),
    )


def clean_options(options):
    return sorted({option for option in options if option[1] and option[1].strip()})


class SalesforceAccountIDFilter(BaseAccountingSingleOptionFilter):
    slug = 'salesforce_account_id'
    label = _("Salesforce Account ID")
    default_text = _("Any")
    async_handler = AccountFilterAsyncHandler
    async_action = 'account_id'


class SubscriberFilter(BaseAccountingSingleOptionFilter):
    slug = 'subscriber'
    label = _('Project Space')
    default_text = _("Any")
    async_handler = SubscriberFilterAsyncHandler
    async_action = 'subscriber'


class SalesforceContractIDFilter(BaseAccountingSingleOptionFilter):
    slug = 'salesforce_contract_id'
    label = _('Salesforce Contract ID')
    default_text = _("Any")
    async_handler = SubscriptionFilterAsyncHandler
    async_action = 'contract_id'


class ActiveStatusFilter(BaseSingleOptionFilter):
    slug = 'active_status'
    label = _('Active Status')
    default_text = _("Any")
    active = 'Active'
    inactive = 'Inactive'
    options = [
        (active, active),
        (inactive, inactive),
    ]


class CustomerAccountFilter(BaseSingleOptionFilter):
    slug = 'customer_account'
    label = _('Customer Billing Account')
    default_text = _("Any")
    is_customer_account = 'Yes'
    is_not_customer_account = 'No'
    options = [
        (is_customer_account, is_customer_account),
        (is_not_customer_account, is_not_customer_account),
    ]


class DimagiContactFilter(BaseAccountingSingleOptionFilter):
    slug = 'dimagi_contact'
    label = _('Dimagi Contact')
    default_text = _("Any")
    async_handler = AccountFilterAsyncHandler
    async_action = 'dimagi_contact'


class EntryPointFilter(BaseSingleOptionFilter):
    slug = 'entry_point'
    label = _('Entry Point')
    default_text = _("Any")
    options = EntryPoint.CHOICES


class DoNotInvoiceFilter(BaseSingleOptionFilter):
    slug = 'do_not_invoice'
    label = _('Invoicing Status')
    default_text = _('Any')

    INVOICE = "SEND_INVOICE"
    DO_NOT_INVOICE = "DO_NOT_INVOICE"
    options = [
        (INVOICE, _('Send invoice')),
        (DO_NOT_INVOICE, _('Do not invoice')),
    ]


class TrialStatusFilter(BaseSingleOptionFilter):
    slug = 'trial_status'
    label = _("Trial Status")
    default_text = _("Show All Subscriptions (including trials)")
    TRIAL = "trial"
    NON_TRIAL = "non_trial"
    options = [
        (NON_TRIAL, _("Show Non-Trial Subscriptions")),
        (TRIAL, _("Show Only Trial Subscriptions")),
    ]


class SubscriptionTypeFilter(BaseSingleOptionFilter):
    slug = 'service_type'
    label = _("Type")
    default_text = _("Any")
    options = SubscriptionType.CHOICES


class ProBonoStatusFilter(BaseSingleOptionFilter):
    slug = 'pro_bono_status'
    label = _("Discounted")
    default_text = _("Any")
    options = ProBonoStatus.CHOICES


class IsHiddenFilter(BaseSingleOptionFilter):
    slug = 'is_hidden'
    label = _('Is Hidden')
    default_text = _('All')
    IS_HIDDEN = 'hidden'
    IS_NOT_HIDDEN = 'not_hidden'
    options = [
        (IS_HIDDEN, 'Is Hidden'),
        (IS_NOT_HIDDEN, 'Is Not Hidden'),
    ]


class CreatedSubAdjMethodFilter(BaseSingleOptionFilter):
    """
    For filtering whether the initial subscription adjustment was
    was internal or user-created.
    """
    slug = "sub_adj_method"
    label = _("Created By")
    default_text = _("Anyone")
    options = (
        (SubscriptionAdjustmentMethod.INTERNAL, "Operations Created"),
        (SubscriptionAdjustmentMethod.USER, "User Created"),
        (SubscriptionAdjustmentMethod.INVOICING, "Created During Invoicing"),
        (SubscriptionAdjustmentMethod.TASK, "[Deprecated] Created During Invoicing"),
        (SubscriptionAdjustmentMethod.TRIAL, "30 Day Trial (default signup)"),
        (SubscriptionAdjustmentMethod.DEFAULT_COMMUNITY, "Defaulted to Community"),
    )


class DateRangeFilter(BaseReportFilter):
    template = 'reports/filters/daterange.html'
    default_days = 7

    START_DATE = 'startdate'
    END_DATE = 'enddate'

    @property
    def filter_context(self):
        return {
            'datespan': self.datespan,
        }

    @classmethod
    def get_date_str(cls, request, date_type):
        return request.GET.get('%s_%s' % (cls.slug, date_type))

    @classmethod
    def get_date(cls, request, date_type):
        date_str = cls.get_date_str(request, date_type)
        if date_str is not None:
            try:
                return datetime.datetime.combine(
                    iso_string_to_date(date_str), datetime.time())
            except ValueError:
                if date_type == cls.START_DATE:
                    return datetime.datetime.today() - datetime.timedelta(days=cls.default_days)
                elif date_type == cls.END_DATE:
                    return datetime.datetime.today()
                else:
                    return None
        else:
            return None

    @classmethod
    def get_start_date(cls, request):
        return cls.get_date(request, cls.START_DATE)

    @classmethod
    def get_end_date(cls, request):
        return cls.get_date(request, cls.END_DATE)

    @property
    def datespan(self):
        datespan = DateSpan.since(self.default_days,
                                  enddate=datetime.date.today(),
                                  timezone=self.timezone)
        if self.get_start_date(self.request) is not None:
            datespan.startdate = self.get_start_date(self.request)
        if self.get_end_date(self.request) is not None:
            datespan.enddate = self.get_end_date(self.request)
        return datespan

    @classmethod
    def shared_pagination_GET_params(cls, request):
        return [
            {'name': '%s_%s' % (cls.slug, date), 'value': cls.get_date_str(request, date)}
            for date in [cls.START_DATE, cls.END_DATE]
        ]


class OptionalFilterMixin(object):

    @classmethod
    def use_filter(cls, request):
        return cls.optional_filter_string_value(request) == 'on'

    @classmethod
    def optional_filter_slug(cls):
        return "report_filter_%s_use_filter" % cls.slug

    @classmethod
    def optional_filter_string_value(cls, request):
        return request.GET.get(cls.optional_filter_slug(), None)


class OptionalDateRangeFilter(DateRangeFilter, OptionalFilterMixin):
    template = 'reports/filters/optional_daterange.html'

    @property
    def filter_context(self):
        context = super(OptionalDateRangeFilter, self).filter_context
        context.update({
            'showFilterName': self.use_filter(self.request),
        })
        return context


class DateFilter(OptionalDateRangeFilter):
    slug = 'date'
    label = "Date"


class DateCreatedFilter(OptionalDateRangeFilter):
    slug = 'date_created'
    label = _("Date Created")


class StartDateFilter(OptionalDateRangeFilter):
    slug = 'start_date'
    label = _("Start Date")


class EndDateFilter(OptionalDateRangeFilter):
    slug = 'end_date'
    label = _("End Date")


class OptionalMonthYearFilter(BaseReportFilter, OptionalFilterMixin):
    template = 'reports/filters/optional_month_year.html'

    @property
    def filter_context(self):
        context = {}
        context.update({
            'showFilterName': self.use_filter(self.request),
            'months': self.months(),
            'years': list(range(2013, datetime.date.today().year + 1)),
            'selected_period': self.selected_period(),
        })
        return context

    @classmethod
    def get_value(cls, request, domain):
        if not cls.use_filter(request):
            return None
        month = int(request.GET.get("report_filter_%s_month" % cls.slug))
        year = int(request.GET.get("report_filter_%s_year" % cls.slug))
        last_day_of_month = calendar.monthrange(year, month)[1]
        return (datetime.date(year, month, 1),
                datetime.date(year, month, last_day_of_month))

    @classmethod
    def months(cls):
        month_pairs = []
        for month_number in range(1, 13):
            month_pairs.append({
                'name': calendar.month_name[month_number],
                'value': month_number,
            })
        return month_pairs

    def selected_period(self):
        today = datetime.date.today()
        month = today.month
        year = today.year
        period = self.get_value(self.request, self.domain)
        if period is not None:
            month = period[0].month
            year = period[0].year
        return {
            'month': month,
            'year': year,
        }


class StatementPeriodFilter(OptionalMonthYearFilter):
    slug = 'statement_period'
    label = _("Statement Period")

    def selected_period(self):
        period = self.get_value(self.request, self.domain)
        if period is not None:
            month = period[0].month
            year = period[0].year
        else:
            today = datetime.date.today()
            one_month_ago = today - relativedelta(months=1)
            month = one_month_ago.month
            year = one_month_ago.year

        return {
            'month': month,
            'year': year,
        }


class DueDatePeriodFilter(OptionalMonthYearFilter):
    slug = 'due_date'
    label = _("Due Date")


class SoftwarePlanNameFilter(BaseAccountingSingleOptionFilter):
    slug = 'plan_name'
    label = _("Plan Name")
    default_text = _("All")
    async_handler = SoftwarePlanAsyncHandler
    async_action = 'name'


class SoftwarePlanEditionFilter(BaseSingleOptionFilter):
    slug = 'edition'
    label = _("Edition")
    default_text = _("All")
    options = SoftwarePlanEdition.CHOICES


class SoftwarePlanVisibilityFilter(BaseSingleOptionFilter):
    slug = 'visibility'
    label = _("Visibility")
    default_text = _("All")
    options = SoftwarePlanVisibility.CHOICES


class InvoiceNumberFilter(BaseAccountingSingleOptionFilter):
    slug = 'invoice_number'
    label = 'Invoice Number'
    default_text = 'All'
    async_handler = InvoiceNumberAsyncHandler
    async_action = 'invoice_number'


class CustomerInvoiceNumberFilter(BaseAccountingSingleOptionFilter):
    slug = 'customer_invoice_number'
    label = 'Customer Invoice Number'
    default_text = 'All'
    async_handler = CustomerInvoiceNumberAsyncHandler
    async_action = 'customer_invoice_number'


class InvoiceBalanceFilter(BaseAccountingSingleOptionFilter):
    slug = 'invoice_balance'
    label = 'Invoice Balance'
    default_text = 'All'
    async_handler = InvoiceBalanceAsyncHandler
    async_action = 'invoice_balance'


class PaymentStatusFilter(BaseSingleOptionFilter):
    slug = 'payment_status'
    label = _("Payment Status")
    default_text = _("All")
    PAID = "paid"
    NOT_PAID = "not_paid"
    options = (
        (PAID, "Paid"),
        (NOT_PAID, "Not Paid"),
    )


class BillingContactFilter(BaseAccountingSingleOptionFilter):
    slug = 'billing_contact'
    label = _("Billing Contact Name")
    default_text = _("All")
    async_handler = BillingContactInfoAsyncHandler
    async_action = 'contact_name'


class PaymentTransactionIdFilter(BaseSimpleFilter):
    slug = "transaction_id"
    label = _("Transaction ID")
    help_inline = _("Usually begins with 'ch_'")
