import datetime
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from corehq.apps.crud.models import BaseAdminHQTabularCRUDManager
from dimagi.utils.data.crud import CRUDFormRequestManager


class IndicatorCRUDFormRequestManager(CRUDFormRequestManager):
    """
        Form request manager for Indicator CRUD forms.
    """
    def _get_form(self):
        if self.request.method == 'POST' and not self.success:
            return self.form_class(self.request.POST, doc_id=self.doc_id, domain=self.request.domain)
        return self.form_class(doc_id=self.doc_id, domain=self.request.domain)


class IndicatorAdminCRUDManager(BaseAdminHQTabularCRUDManager):
    """
        Base CRUDManager for Indicator Definitions
    """
    domain = None

    @property
    def properties_in_row(self):
        return ["slug", "namespace", "version", "last_modified"]

    def format_property(self, key, property):
        if isinstance(property, datetime.datetime):
            return property.strftime("%d %B %Y")
        return super(IndicatorAdminCRUDManager, self).format_property(key, property)

    def create(self, **kwargs):
        namespace = kwargs['namespace']
        del kwargs['namespace']
        self.document_instance = self.document_class.update_or_create_unique(namespace, self.domain, **kwargs)

    def update(self, **kwargs):
        self.document_instance.last_modified = datetime.datetime.utcnow()
        super(IndicatorAdminCRUDManager, self).update(**kwargs)


class FormLabelIndicatorAdminCRUDManager(IndicatorAdminCRUDManager):

    @property
    def properties_in_row(self):
        original_props = super(FormLabelIndicatorAdminCRUDManager, self).properties_in_row
        return original_props[:2] + ["xmlns"] + original_props[-2:]


class BaseFormIndicatorAdminCRUDManager(FormLabelIndicatorAdminCRUDManager):

    def format_property(self, key, property):
        if key == "xmlns":
            from corehq.apps.indicators.models import FormLabelIndicatorDefinition
            label = FormLabelIndicatorDefinition.get_label_for_xmlns(self.document_instance.namespace,
                                                                     self.document_instance.domain, property)
            return mark_safe(render_to_string("indicators/partials/form_label.html", {
                "label": label,
                "xmlns": property,
            }))
        return super(BaseFormIndicatorAdminCRUDManager, self).format_property(key, property)


class FormAliasIndicatorAdminCRUDManager(BaseFormIndicatorAdminCRUDManager):

    @property
    def properties_in_row(self):
        original_props = super(FormAliasIndicatorAdminCRUDManager, self).properties_in_row
        return original_props[:3] + ["question_id"] + original_props[-2:]

