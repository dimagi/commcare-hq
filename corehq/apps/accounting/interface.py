from corehq.apps.accounting.dispatcher import AccountingAdminInterfaceDispatcher
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.announcements.forms import HQAnnouncementForm
from corehq.apps.announcements.models import HQAnnouncement
from corehq.apps.crud.interface import BaseCRUDAdminInterface
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn


class AccountingInterface(BaseCRUDAdminInterface):
    section_name = "Accounting"
    base_template = 'reports/base_template.html'
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
            DataTablesColumn("Client/Account Name"),
            DataTablesColumn("Billing Contact Name (Email)"),
            DataTablesColumn("Plan Credit"),
            DataTablesColumn("SMS Credit"),
            DataTablesColumn("Users Credit"),
            DataTablesColumn("Account Balance"),
            DataTablesColumn("Active Subscriptions"),
            DataTablesColumn("Edit"),
        )

    @property
    def rows(self):
        rows = []
        for account in BillingAccount.objects.all():
            rows.append([account.name,
                         account.web_user_contact,
                         3,
                         4,
                         5,
                         account.balance,
                         7,
                         'edit button!'])
        return rows

    #######

    name = "View Billing Accounts"
    description = "description of view billing accounts"
    slug = "accounts"

    document_class = HQAnnouncement
    form_class = HQAnnouncementForm

    crud_item_type = "Billing Account"
