from django.core.urlresolvers import reverse
from corehq.apps.adm.dispatcher import ADMAdminInterfaceDispatcher
from corehq.apps.crud.interface import BaseCRUDAdminInterface

class BaseADMAdminInterface(BaseCRUDAdminInterface):
    # overrides
    section_name = "Global ADM Report Configuration"
    app_slug = 'adm'
    dispatcher = ADMAdminInterfaceDispatcher

    crud_item_type = "ADM Item"
    crud_form_update_url = "/adm/form/"

    def validate_document_class(self):
        from corehq.apps.adm.models import BaseADMDocument
        if self.document_class is None or not issubclass(self.document_class, BaseADMDocument):
            raise NotImplementedError("document_class must be an ADMColumn or an "
                                      "ADMReport and must not be None.")

    @property
    def template_context(self):
        context = super(BaseADMAdminInterface, self).template_context
        context.update(adm_admin=True)
        return context

    @property
    def default_report_url(self):
        return reverse("default_adm_admin_interface")

