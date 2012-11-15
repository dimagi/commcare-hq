from couchdbkit.ext.django.schema import Document, StringProperty, DateTimeProperty, StringListProperty
from corehq.apps.announcements.crud import HQAnnouncementCRUDManager
from dimagi.utils.decorators.memoized import memoized

class HQAnnouncement(Document):
    """
        For global, site-wide HQ Announcements.
    """
    title = StringProperty()
    summary = StringProperty()
    highlighted_elements = StringListProperty()
    date_created = DateTimeProperty()
    valid_until = DateTimeProperty()

    base_doc = "HQAnnouncement"

    _crud_class = HQAnnouncementCRUDManager

    @property
    @memoized
    def crud(self):
        return self._crud_class(self.__class__, self)

    @classmethod
    def get_crud(cls):
        return cls._crud_class(cls)
