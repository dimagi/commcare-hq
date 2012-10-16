from django.core.urlresolvers import reverse
from corehq.apps.adm.dispatcher import ADMAdminInterfaceDispatcher
from corehq.apps.reports.generic import GenericTabularReport

class BaseADMAdminInterface(GenericTabularReport):
    # overrides
    section_name = "Global ADM Report Configuration"
    app_slug = 'adm'
    dispatcher = ADMAdminInterfaceDispatcher
    asynchronous = True
    hide_filters = True
    report_template_path = "adm/interfaces/adm_tabular.html"

    # new
    property_class = None
    form_class = None

    detailed_description = ""
    adm_item_type = "ADM Item"

    def __init__(self, request, base_context=None, *args, **kwargs):
        from dimagi.utils.data.crud import BaseCRUDForm
        from corehq.apps.adm.models import BaseADMDocument
        if self.property_class is None or not issubclass(self.property_class, BaseADMDocument):
            raise NotImplementedError("property_class must be an ADMColumn or an "
                                      "ADMReport and must not be None.")
        if self.form_class is None or not issubclass(self.form_class, BaseCRUDForm):
            raise NotImplementedError('form_class must be a subclass of InterfaceEditableItemForm'
                                      ' and must not be None.')

        super(BaseADMAdminInterface, self).__init__(request, base_context, *args, **kwargs)

    @property
    def template_context(self):
        context = super(BaseADMAdminInterface, self).template_context
        context.update(adm_admin=True)
        return context

    @property
    def report_context(self):
        context = super(BaseADMAdminInterface, self).report_context
        context.update(
            detailed_description=self.detailed_description,
            adm_item = dict(
                type=self.adm_item_type,
                form=self.form_class.__name__
            )
        )
        return context

    @property
    def default_report_url(self):
        return reverse("default_adm_admin_interface")

