from couchdbkit.ext.django.schema import Document, StringProperty, DateTimeProperty, StringListProperty
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
