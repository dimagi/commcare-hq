from django.utils.safestring import mark_safe
from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher, SubscriptionAdminInterfaceDispatcher
from corehq.apps.accounting.models import BillingAccount, Subscription
from corehq.apps.announcements.forms import HQAnnouncementForm
from corehq.apps.announcements.models import HQAnnouncement
from corehq.apps.crud.interface import BaseCRUDAdminInterface
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn


class AccountingInterface(BaseCRUDAdminInterface):
    section_name = "Accounting"
    base_template = 'view_template.html'
    dispatcher = AccountingAdminInterfaceDispatcher

    crud_form_update_url = "/accounting/form/"

    def validate_document_class(self):
        return True
        #if self.document_class is None or not issubclass(self.document_class, HQAnnouncement):
        #    raise NotImplementedError("document_class must be an HQAnnouncement")

    """
    @property
    def default_report_url(self):
        return reverse("default_announcement_admin")
    """

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
            rows.append([mark_safe('<a href="./%d">%s</a>' % (account.id, account.name)),
                         account.salesforce_account_id,
                         account.date_created,
                         account.account_type])
        return rows

    #######

    name = "Billing Accounts"
    description = "description of view billing accounts"
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
        #if self.document_class is None or not issubclass(self.document_class, HQAnnouncement):
        #    raise NotImplementedError("document_class must be an HQAnnouncement")

    """
    @property
    def default_report_url(self):
        return reverse("default_announcement_admin")
    """

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Project Space"),
            DataTablesColumn("Client Name"),
            DataTablesColumn("Version"),
            DataTablesColumn("Description"),
            DataTablesColumn("Account Name"),
            DataTablesColumn("Start Date"),
            DataTablesColumn("End Date"),
            DataTablesColumn("Active Status"),
            DataTablesColumn("Visibility"),
            DataTablesColumn("Is Default for Product?"),
            DataTablesColumn("Edit"),
        )

    @property
    def rows(self):
        rows = []
        for subscription in Subscription.objects.all():
            rows.append([subscription.subscriber.domain,
                         subscription.account.name,
                         subscription.plan.plan.name,
                         subscription.plan.plan.description,
                         mark_safe('<a href="../accounts/%d">%s</a>'
                                   % (subscription.account.id, subscription.account.name)),
                         subscription.date_start,
                         subscription.date_end,
                         subscription.is_active,
                         subscription.plan.plan.visibility,
                         "MISSING VALUE",
                         mark_safe('<a href="./%d" class="btn">Edit</a>' % subscription.id)])
        return rows

    #######

    name = "Subscriptions"
    description = "description of view subscriptions"
    slug = "subscriptions"

    document_class = HQAnnouncement
    form_class = HQAnnouncementForm

    crud_item_type = "Subscription"
