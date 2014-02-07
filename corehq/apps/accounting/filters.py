from corehq.apps.accounting.models import *
from corehq.apps.reports.filters.base import BaseReportFilter, BaseSingleOptionFilter
from dimagi.utils.dates import DateSpan
from django.utils.translation import ugettext_noop as _


class AccountTypeFilter(BaseSingleOptionFilter):
    slug = 'account_type'
    label = _("Account Type")
    default_text = _("All")
    options = BillingAccountType.CHOICES


class NameFilter(BaseSingleOptionFilter):
    slug = 'name'
    label = _("Name")
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
    default_text = _("All")

    @property
    def options(self):
        return clean_options([(account.salesforce_account_id, account.salesforce_account_id)
                              for account in BillingAccount.objects.all()])


class SubscriberFilter(BaseSingleOptionFilter):
    slug = 'subscriber'
    label = _('Subscriber')
    default_text = _("All")

    @property
    def options(self):
        return clean_options([(subscription.subscriber.domain, subscription.subscriber.domain)
                              for subscription in Subscription.objects.all()])


class SalesforceContractIDFilter(BaseSingleOptionFilter):
    slug = 'salesforce_contract_id'
    label = _('Salesforce Contract ID')
    default_text = _("All")

    @property
    def options(self):
        return clean_options([(subscription.salesforce_contract_id, subscription.salesforce_contract_id)
                              for subscription in Subscription.objects.all()])


class ActiveStatusFilter(BaseSingleOptionFilter):
    slug = 'active_status'
    label = _('Active Status')
    default_text = _("All")
    active = 'Active'
    inactive = 'Inactive'
    options = [
        (active, active),
        (inactive, inactive),
    ]


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
        datespan = DateSpan.since(self.default_days, format="%Y-%m-%d", timezone=self.timezone)
        if self.get_start_date(self.request) is not None:
            datespan.startdate = self.get_start_date(self.request)
        if self.get_end_date(self.request) is not None:
            datespan.enddate = self.get_end_date(self.request)
        return datespan


class DateCreatedFilter(DateRangeFilter):
    slug = 'date_created'
    label = _("Date Created")


class StartDateFilter(DateRangeFilter):
    slug = 'start_date'
    label = _("Start Date")


class EndDateFilter(DateRangeFilter):
    slug = 'end_date'
    label = _("End Date")


class SoftwarePlanNameFilter(BaseSingleOptionFilter):
    slug = 'name'
    label = _("Name")
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
