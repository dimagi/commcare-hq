import datetime
from corehq.apps.crud.models import BaseAdminHQTabularCRUDManager

class HQAnnouncementCRUDManager(BaseAdminHQTabularCRUDManager):
    """
        CRUD Manager for HQ Announcements
    """
    @property
    def properties_in_row(self):
        return ["title", "summary", "highlighted_selectors", "date_created", "valid_until"]

    def update(self, **kwargs):
        if not self.document_instance.date_created:
            self.document_instance.date_created = datetime.datetime.utcnow()
        super(HQAnnouncementCRUDManager, self).update(**kwargs)

