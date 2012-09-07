from django.utils.safestring import mark_safe
from corehq.apps.adm.dispatcher import ADMAdminInterfaceDispatcher
from corehq.apps.adm.models import ADMColumn
from corehq.apps.adm.models import ADMReport
from corehq.apps.reports.generic import GenericTabularReport
from dimagi.utils.data.editable_items import InterfaceEditableItemForm

class ADMAdminInterface(GenericTabularReport):
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
        if self.property_class is None or not (issubclass(self.property_class, ADMColumn) or issubclass(self.property_class, ADMReport)):
            raise NotImplementedError("property_class must be an ADMColumn or an ADMReport and must not be None.")
        if self.form_class is None or not issubclass(self.form_class, InterfaceEditableItemForm):
            raise NotImplementedError('form_class must be a subclass of InterfaceEditableItemForm and must not be None.')

        super(ADMAdminInterface, self).__init__(request, base_context, *args, **kwargs)

    @property
    def report_context(self):
        context = super(ADMAdminInterface, self).report_context
        context.update(
            detailed_description=mark_safe(self.detailed_description),
            adm_item = dict(
                type=self.adm_item_type,
                form=self.form_class.__name__
            )
        )
        return context