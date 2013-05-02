import datetime
from markdown import markdown
from corehq.apps.crud.models import BaseAdminHQTabularCRUDManager

class HQAnnouncementCRUDManager(BaseAdminHQTabularCRUDManager):
    """
        CRUD Manager for HQ Announcements
    """
    @property
    def properties_in_row(self):
        return ["title", "summary", "date_created", "valid_until", "show_to_new_users"]

    def format_property(self, key, property):
        if isinstance(property, datetime.datetime):
            return property.strftime("%d %b %Y")
        if key == "summary":
            return markdown(property)
        return super(HQAnnouncementCRUDManager, self).format_property(key, property)


    def update(self, **kwargs):
        if not self.document_instance.date_created:
            self.document_instance.date_created = datetime.datetime.utcnow()
        self.document_instance.valid_until = datetime.datetime.utcnow() + datetime.timedelta(days=35) # temporary
        super(HQAnnouncementCRUDManager, self).update(**kwargs)

