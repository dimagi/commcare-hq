from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.filters import *
from corehq.apps.accounting.models import BillingAccount, Subscription, SoftwarePlan
from corehq.apps.announcements.forms import HQAnnouncementForm
from corehq.apps.announcements.models import HQAnnouncement
from corehq.apps.crud.interface import BaseCRUDAdminInterface
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe


class AccountingInterface(BaseCRUDAdminInterface):
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
            if DateCreatedFilter.get_start_date(self.request).date() <= account.date_created \
                and DateCreatedFilter.get_end_date(self.request).date() >= account.date_created \
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
    dispatcher = AccountingAdminInterfaceDispatcher

    crud_form_update_url = "/accounting/form/"

    fields = ['corehq.apps.accounting.interface.StartDateFilter',
              'corehq.apps.accounting.interface.EndDateFilter',
              'corehq.apps.accounting.interface.DateCreatedFilter',
              'corehq.apps.accounting.interface.SubscriberFilter',
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
            if (subscription.date_start is None
                    or (StartDateFilter.get_start_date(self.request).date() <= subscription.date_start
                        and StartDateFilter.get_end_date(self.request).date() >= subscription.date_start)) \
                and (subscription.date_end is None
                        or (EndDateFilter.get_start_date(self.request).date() <= subscription.date_end
                            and EndDateFilter.get_end_date(self.request).date() >= subscription.date_end)) \
                and (DateCreatedFilter.get_start_date(self.request).date() <= subscription.date_created
                    and DateCreatedFilter.get_end_date(self.request).date() >= subscription.date_created) \
                and (SubscriberFilter.get_value(self.request, self.domain) is None
                    or SubscriberFilter.get_value(self.request, self.domain) == subscription.subscriber.domain) \
                and (SalesforceContractIDFilter.get_value(self.request, self.domain) is None
                    or SalesforceContractIDFilter.get_value(self.request, self.domain) == subscription.salesforce_contract_id) \
                and (ActiveStatusFilter.get_value(self.request, self.domain) is None
                    or (ActiveStatusFilter.get_value(self.request, self.domain) == ActiveStatusFilter.active) == subscription.is_active):
                rows.append([subscription.subscriber.domain,
                             mark_safe('<a href="%s">%s</a>'
                                       % (reverse(ManageBillingAccountView.urlname, args=(subscription.account.id,)),
                                          subscription.account.name)),
                             subscription.plan_version.plan.name,
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


class SoftwarePlanInterface(BaseCRUDAdminInterface):
    section_name = "Accounting"
    base_template = 'accounting/add_software_plan_button.html'
    dispatcher = AccountingAdminInterfaceDispatcher

    crud_form_update_url = "/accounting/form/"

    fields = [
        'corehq.apps.accounting.interface.SoftwarePlanNameFilter',
        'corehq.apps.accounting.interface.SoftwarePlanEditionFilter',
        'corehq.apps.accounting.interface.SoftwarePlanVisibilityFilter',
    ]
    hide_filters = False

    def validate_document_class(self):
        return True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Name"),
            DataTablesColumn("Description"),
            DataTablesColumn("Edition"),
            DataTablesColumn("Visibility"),
            DataTablesColumn("Date of Last Version"),
        )

    @property
    def rows(self):
        rows = []
        for plan in SoftwarePlan.objects.all():
            name = SoftwarePlanNameFilter.get_value(self.request, self.domain)
            edition = SoftwarePlanEditionFilter.get_value(self.request, self.domain)
            visibility = SoftwarePlanVisibilityFilter.get_value(self.request, self.domain)
            if ((name is None or name == plan.name)
                and (edition is None or edition == plan.edition)
                and (visibility is None or visibility == plan.visibility)):
                rows.append([
                    mark_safe('<a href="./%d">%s</a>' % (plan.id, plan.name)),
                    plan.description,
                    plan.edition,
                    plan.visibility,
                    SoftwarePlan.objects.get(id=plan.id).get_version().date_created
                        if len(SoftwarePlanVersion.objects.filter(plan=plan)) != 0 else 'N/A',
                ])
        return rows

    @property
    def report_context(self):
        context = super(SoftwarePlanInterface, self).report_context
        context.update(
            hideButton=True,
        )
        return context

    name = "Software Plans"
    description = "List of all software plans"
    slug = "software_plans"

    document_class = HQAnnouncement
    form_class = HQAnnouncementForm

    crud_item_type = "Software_Plan"
