from django.utils.safestring import mark_safe
from dimagi.utils.data.crud import TabularCRUDManager

class HQAnnouncementCRUDManager(TabularCRUDManager):
    """
        CRUD Manager for HQ Announcements
    """
    @property
    def edit_button(self):
        doc_id = self.document_instance.get_id if self.document_instance else ""
        return mark_safe("""<a href="#crud_update_modal"
            class="btn"
            data-item_id="%s"
            onclick="crud_interface.update_item(this)"
            data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" % doc_id)

