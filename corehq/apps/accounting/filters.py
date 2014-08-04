import calendar
from corehq.apps.accounting.models import *
from corehq.apps.reports.filters.base import (
    BaseReportFilter, BaseSingleOptionFilter
)
from corehq.apps.reports.filters.search import SearchFilter
from dimagi.utils.dates import DateSpan
from django.utils.translation import ugettext_noop as _


class AccountTypeFilter(BaseSingleOptionFilter):
    slug = 'account_type'
    label = _("Account Type")
    default_text = _("All")
    options = BillingAccountType.CHOICES


class NameFilter(BaseSingleOptionFilter):
    slug = 'account_name'
    label = _("Account Name")
    default_text = _("All")

    @property
    def options(self):
        return [(account.name, account.name) for account in BillingAccount.objects.all()]


def clean_options(options):
    cleaned_options = []
    for option in options:
        if option[1] is not None and option[1].strip() != '':
            cleaned_options.append(option)
    return sorted([_ for _ in set(cleaned_options)])


class SalesforceAccountIDFilter(BaseSingleOptionFilter):
    slug = 'salesforce_account_id'
    label = _("Salesforce Account ID")
    default_text = _("Any")

    @property
    def options(self):
        return clean_options([(account.salesforce_account_id, account.salesforce_account_id)
                              for account in BillingAccount.objects.all()])


class SubscriberFilter(BaseSingleOptionFilter):
    slug = 'subscriber'
    label = _('Project Space')
    default_text = _("Any")

    @property
    def options(self):
        return clean_options([(subscription.subscriber.domain, subscription.subscriber.domain)
                              for subscription in Subscription.objects.all()])


class SalesforceContractIDFilter(BaseSingleOptionFilter):
    slug = 'salesforce_contract_id'
    label = _('Salesforce Contract ID')
    default_text = _("Any")

    @property
    def options(self):
        return clean_options([(subscription.salesforce_contract_id, subscription.salesforce_contract_id)
                              for subscription in Subscription.objects.all()])


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


INVOICE = "SEND_INVOICE"
DO_NOT_INVOICE = "DO_NOT_INVOICE"


class DoNotInvoiceFilter(BaseSingleOptionFilter):
    slug = 'do_not_invoice'
    label = _('Invoicing Status')
    default_text = _('Any')
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
        (TRIAL, _("Show Non-Trial Subscriptions")),
        (NON_TRIAL, _("Show Only Trial Subscriptions")),
    ]


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
        (SubscriptionAdjustmentMethod.TASK, "Created During Invoicing"),
    )


class DateRangeFilter(BaseReportFilter):
    template = 'reports/filters/daterange.html'
    default_days = 7

    @property
    def datepicker_config(self):
        return {
            'changeMonth': True,
            'changeYear': True,
            'dateFormat': 'yy-mm-dd',
        }

    @property
    def filter_context(self):
        return {
            'datepicker_config': self.datepicker_config,
            'datespan': self.datespan,
        }

    @classmethod
    def get_date_str(cls, request, date_type):
        return request.GET.get('%s_%s' % (cls.slug, date_type))

    @classmethod
    def get_date(cls, request, date_type):
        date_str = cls.get_date_str(request, date_type)
        if date_str is not None:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d")
        else:
            return None

    @classmethod
    def get_start_date(cls, request):
        return cls.get_date(request, 'startdate')

    @classmethod
    def get_end_date(cls, request):
        return cls.get_date(request, 'enddate')

    @property
    def datespan(self):
        datespan = DateSpan.since(self.default_days,
                                  enddate=datetime.date.today(),
                                  format="%Y-%m-%d",
                                  timezone=self.timezone)
        if self.get_start_date(self.request) is not None:
            datespan.startdate = self.get_start_date(self.request)
        if self.get_end_date(self.request) is not None:
            datespan.enddate = self.get_end_date(self.request)
        return datespan


class OptionalFilterMixin(object):
    @classmethod
    def use_filter(cls, request):
        return request.GET.get(
            "report_filter_%s_use_filter" % cls.slug, None) == 'on'


class OptionalDateRangeFilter(DateRangeFilter, OptionalFilterMixin):
    template = 'reports/filters/optional_daterange.html'

    @property
    def filter_context(self):
        context = super(OptionalDateRangeFilter, self).filter_context
        context.update({
            'showFilterName': self.use_filter(self.request),
        })
        return context

    @classmethod
    def date_passes_filter(cls, request, date):
        return (date is None or not cls.use_filter(request) or
            (super(OptionalDateRangeFilter, cls).get_start_date(request).date() <= date
                and super(OptionalDateRangeFilter, cls).get_end_date(request).date() >= date))


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
            'years': range(2013, datetime.date.today().year + 1),
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
        for month_number in range(12):
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


class DueDatePeriodFilter(OptionalMonthYearFilter):
    slug = 'due_date'
    label = _("Due Date")


class SoftwarePlanNameFilter(BaseSingleOptionFilter):
    slug = 'plan_name'
    label = _("Plan Name")
    default_text = _("All")

    @property
    def options(self):
        return clean_options([(account.name, account.name) for account in SoftwarePlan.objects.all()])


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


class BillingContactFilter(BaseSingleOptionFilter):
    slug = 'billing_contact'
    label = _("Billing Contact Name")
    default_text = _("All")

    @property
    def options(self):
        return clean_options(
            [
                (contact.full_name, contact.full_name)
                for contact in BillingContactInfo.objects.all()
                if contact.first_name or contact.last_name
            ]
        )


class PaymentTransactionIdFilter(SearchFilter):
    slug = "transaction_id"
    label = _("Transaction ID")
    search_help_inline = _("Usually begins with 'ch_'")

