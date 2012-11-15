from django.utils.safestring import mark_safe
from dimagi.utils.data.crud import TabularCRUDManager, BaseCRUDForm
from dimagi.utils.decorators.memoized import memoized

class BaseHQTabularCRUDManager(TabularCRUDManager):
    """
        All Tabular CRUD Managers for CoreHQ-based CRUD should extend this.
    """
    @property
    def edit_button(self):
        doc_id = self.document_instance.get_id if self.document_instance else ""
        return mark_safe("""<a href="#updateHQAnnouncementModal"
            class="btn"
            data-item_id="%s"
            onclick="adm_interface.update_item(this)"
            data-toggle="modal"><i class="icon icon-pencil"></i> Edit</a>""" % doc_id)

    def update(self, **kwargs):
        for key, item in kwargs.items():
            try:
                setattr(self.document_instance, key, item)
            except AttributeError:
                pass
        self.document_instance.save()

    def create(self, **kwargs):
        self.document_instance = self.document_class()
        self.update(**kwargs)


class AdminCRUDDocumentMixin(object):
    """
        Mixin for Administrative CRUD Managers in Documents.
    """
    _admin_crud_class = None

    @property
    @memoized
    def admin_crud(self):
        return self._admin_crud_class(self.__class__, self)

    @classmethod
    def get_admin_crud(cls):
        return cls._admin_crud_class(cls)


class BaseAdminCRUDForm(BaseCRUDForm):
    """
        Use this for all forms that are associated with documents using the AdminCRUDDocumentMixin.
    """
    @property
    @memoized
    def crud_manager(self):
        if self.existing_object:
            return self.existing_object.admin_crud
        return self.doc_class.get_admin_crud()
