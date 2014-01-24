from django.core.urlresolvers import reverse
from corehq.apps.announcements.dispatcher import HQAnnouncementAdminInterfaceDispatcher
from corehq.apps.announcements.forms import HQAnnouncementForm, ReportAnnouncementForm
from corehq.apps.announcements.models import HQAnnouncement, ReportAnnouncement
from corehq.apps.crud.interface import BaseCRUDAdminInterface
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn


class BaseHQAnnouncementsAdminInterface(BaseCRUDAdminInterface):
    section_name = "HQ Announcements"
    base_template = 'reports/base_template.html'
    dispatcher = HQAnnouncementAdminInterfaceDispatcher

    crud_form_update_url = "/announcements/form/"

    def validate_document_class(self):
        if self.document_class is None or not issubclass(self.document_class, HQAnnouncement):
            raise NotImplementedError("document_class must be an HQAnnouncement")

    @property
    def default_report_url(self):
        return reverse("default_announcement_admin")

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Title"),
            DataTablesColumn("Summary"),
            DataTablesColumn("Date Created"),
            DataTablesColumn("Valid Until"),
            DataTablesColumn("Show to new users?"),
            DataTablesColumn("Edit"),
        )

    @property
    def rows(self):
        rows = []
        for item in self.announcements:
            rows.append(item.admin_crud.row)
        return rows

    @property
    def announcements(self):
        key = ["type", self.document_class.__name__]
        data = self.document_class.view('announcements/all_announcements',
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key + [{}],
            #stale=settings.COUCH_STALE_QUERY,
        ).all()
        return data


class ManageGlobalHQAnnouncementsInterface(BaseHQAnnouncementsAdminInterface):
    name = "Manage Global HQ Announcements"
    description = "Create Global HQ Announcements here."
    slug = "global_announcements"

    document_class = HQAnnouncement
    form_class = HQAnnouncementForm

    crud_item_type = "Global Announcement"

class ManageReportAnnouncementsInterface(BaseHQAnnouncementsAdminInterface):
    name = "Manage Report Announcements"
    description = "Create Report Announcements Here"
    slug = "report_announcements"

    document_class = ReportAnnouncement
    form_class = ReportAnnouncementForm

    crud_item_type = "Report Announcement"




