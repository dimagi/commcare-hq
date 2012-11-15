from corehq.apps.reports.generic import GenericTabularReport

class BaseCRUDAdminInterface(GenericTabularReport):
    asynchronous = True
    hide_filters = True
    report_template_path = "crud/interfaces/crud.tabular.html"

    # new
    document_class = None
    form_class = None

    detailed_description = ""
    crud_item_type = ""
    crud_form_update_url = ""

    def __init__(self, request, base_context=None, *args, **kwargs):
        self.validate_document_class()
        from dimagi.utils.data.crud import BaseCRUDForm
        if self.form_class is None or not issubclass(self.form_class, BaseCRUDForm):
            raise NotImplementedError('form_class must be a subclass of InterfaceEditableItemForm'
                                      ' and must not be None.')

        super(BaseCRUDAdminInterface, self).__init__(request, base_context, *args, **kwargs)

    def validate_document_class(self):
        raise NotImplementedError("Validation of document_class class does not exist.")

    @property
    def report_context(self):
        context = super(BaseCRUDAdminInterface, self).report_context
        context.update(
            detailed_description=self.detailed_description,
            crud_item = {
                'type': self.crud_item_type,
                'form': self.form_class.__name__,
                'url': self.crud_form_update_url,
            },
        )
        return context