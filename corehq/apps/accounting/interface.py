from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher, SubscriptionAdminInterfaceDispatcher
from corehq.apps.accounting.models import BillingAccount, Subscription, BillingAccountType
from corehq.apps.announcements.forms import HQAnnouncementForm
from corehq.apps.announcements.models import HQAnnouncement
from corehq.apps.crud.interface import BaseCRUDAdminInterface
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.standard import DatespanMixin
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
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
    options = [(account.name, account.name) for account in BillingAccount.objects.all()]


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
    options = clean_options([(account.salesforce_account_id, account.salesforce_account_id)
                             for account in BillingAccount.objects.all()])


class SubscriberFilter(BaseSingleOptionFilter):
    slug = 'subscriber'
    label = _('Subscriber')
    default_text = _("All")
    options = clean_options([(subscription.subscriber.domain, subscription.subscriber.domain)
                             for subscription in Subscription.objects.all()])


class SalesforceContractIDFilter(BaseSingleOptionFilter):
    slug = 'salesforce_contract_id'
    label = _('Salesforce Contract ID')
    default_text = _("All")
    options = clean_options([(subscription.salesforce_contract_id, subscription.salesforce_contract_id)
                             for subscription in Subscription.objects.all()])


class ActiveStatusFilter(BaseSingleOptionFilter):
    slug = 'active_status'
    label = _('Active Status')
    default_text = _("All")
    active = 'Active'
    inactive = 'Inactive'
    options = [(active, active),
               (inactive, inactive),
               ]


class DateCreatedFilter(DatespanFilter):
    label = _("Date Created")


class AccountingInterface(BaseCRUDAdminInterface, DatespanMixin):
    section_name = "Accounting"
    base_template = 'accounting/add_account_button.html'
    dispatcher = AccountingAdminInterfaceDispatcher

    crud_form_update_url = "/accounting/form/"

    fields = ['corehq.apps.accounting.interface.DateCreatedFilter',
              'corehq.apps.accounting.interface.NameFilter',
              'corehq.apps.accounting.interface.SalesforceAccountIDFilter',
              'corehq.apps.accounting.interface.AccountTypeFilter',
              ]
    hide_filters = False

    def validate_document_class(self):
        return True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name"),
            DataTablesColumn("Salesforce Account ID"),
            DataTablesColumn("Date Created"),
            DataTablesColumn("Account Type"),
        )

    @property
    def rows(self):
        rows = []
        for account in BillingAccount.objects.all():
            if self.datespan.startdate.date() <= account.date_created \
                and self.datespan.enddate.date() >= account.date_created \
                and (NameFilter.get_value(self.request, self.domain) is None
                     or NameFilter.get_value(self.request, self.domain) == account.name) \
                and (SalesforceAccountIDFilter.get_value(self.request, self.domain) is None
                     or SalesforceAccountIDFilter.get_value(self.request, self.domain) == account.salesforce_account_id) \
                and (AccountTypeFilter.get_value(self.request, self.domain) is None
                     or AccountTypeFilter.get_value(self.request, self.domain) == account.account_type):
                rows.append([mark_safe('<a href="./%d">%s</a>' % (account.id, account.name)),
                             account.salesforce_account_id,
                             account.date_created,
                             account.account_type])
        return rows

    @property
    def report_context(self):
        context = super(AccountingInterface, self).report_context
        context.update(
            hideButton=True,
        )
        return context

    name = "Billing Accounts"
    description = "List of all billing accounts"
    slug = "accounts"

    document_class = HQAnnouncement
    form_class = HQAnnouncementForm

    crud_item_type = "Billing Account"


class SubscriptionInterface(BaseCRUDAdminInterface):
    section_name = "Accounting"
    base_template = 'reports/base_template.html'
    dispatcher = SubscriptionAdminInterfaceDispatcher

    crud_form_update_url = "/accounting/form/"

    fields = ['corehq.apps.accounting.interface.SubscriberFilter',
              'corehq.apps.accounting.interface.SalesforceContractIDFilter',
              'corehq.apps.accounting.interface.ActiveStatusFilter',
              ]
    hide_filters = False

    def validate_document_class(self):
        return True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Subscriber"),
            DataTablesColumn("Account"),
            DataTablesColumn("Plan"),
            DataTablesColumn("Active"),
            DataTablesColumn("Salesforce Contract ID"),
            DataTablesColumn("Start Date"),
            DataTablesColumn("End Date"),
            DataTablesColumn("Action"),
        )

    @property
    def rows(self):
        from corehq.apps.accounting.views import ManageBillingAccountView
        rows = []
        for subscription in Subscription.objects.all():
            if (SubscriberFilter.get_value(self.request, self.domain) is None
                or SubscriberFilter.get_value(self.request, self.domain) == subscription.subscriber.domain) \
                and (SalesforceContractIDFilter.get_value(self.request, self.domain) is None
                    or SalesforceContractIDFilter.get_value(self.request, self.domain) == subscription.salesforce_contract_id) \
                and (ActiveStatusFilter.get_value(self.request, self.domain) is None
                    or (ActiveStatusFilter.get_value(self.request, self.domain) == ActiveStatusFilter.active) == subscription.is_active):
                rows.append([subscription.subscriber.domain,
                             mark_safe('<a href="%s">%s</a>'
                                       % (reverse(ManageBillingAccountView.name, args=(subscription.account.id,)),
                                          subscription.account.name)),
                             subscription.plan.plan.name,
                             subscription.is_active,
                             subscription.salesforce_contract_id,
                             subscription.date_start,
                             subscription.date_end,
                             mark_safe('<a href="./%d" class="btn">Edit</a>' % subscription.id)])

        return rows

    @property
    def report_context(self):
        context = super(SubscriptionInterface, self).report_context
        context.update(
            hideButton=True,
        )
        return context

    name = "Subscriptions"
    description = "List of all subscriptions"
    slug = "subscriptions"

    document_class = HQAnnouncement
    form_class = HQAnnouncementForm

    crud_item_type = "Subscription"
