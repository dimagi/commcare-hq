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


class DateCreatedFilter(DatespanFilter):
    label = _("Date Created")


class AccountingInterface(BaseCRUDAdminInterface, DatespanMixin):
    section_name = "Accounting"
    base_template = 'accounting/add_account_button.html'
    dispatcher = AccountingAdminInterfaceDispatcher

    crud_form_update_url = "/accounting/form/"

    fields = ['corehq.apps.accounting.interface.AccountTypeFilter',
              'corehq.apps.accounting.interface.DateCreatedFilter',
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
