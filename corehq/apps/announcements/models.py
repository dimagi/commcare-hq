from couchdbkit.ext.django.schema import Document, StringProperty, DateTimeProperty, StringListProperty
from django.template.loader import render_to_string
from corehq.apps.announcements.crud import HQAnnouncementCRUDManager
from corehq.apps.crud.models import AdminCRUDDocumentMixin
from dimagi.utils.decorators.memoized import memoized

class HQAnnouncement(Document, AdminCRUDDocumentMixin):
    """
        For global, site-wide HQ Announcements.
    """
    title = StringProperty()
    summary = StringProperty()
    highlighted_selectors = StringListProperty()
    date_created = DateTimeProperty()
    valid_until = DateTimeProperty()

    base_doc = "HQAnnouncement"

    _admin_crud_class = HQAnnouncementCRUDManager

    @property
    def as_html(self):
        return render_to_string("announcements/partials/base_announcement.html", {
            'title': self.title,
            'content': self.summary,
            'announcement_id': self._id,
        })


class ReportAnnouncement(HQAnnouncement):
    """
        Eventually this can have report-specific functionality. For now it's just a placeholder to differentiate from
        Global Announcements.
    """
    pass
