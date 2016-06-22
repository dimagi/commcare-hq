import datetime
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from corehq.apps.crud.models import BaseAdminHQTabularCRUDManager
from corehq.apps.indicators.utils import get_namespace_name
from corehq.const import USER_DATE_FORMAT
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
            return property.strftime(USER_DATE_FORMAT)
        if key == "namespace":
            return get_namespace_name(self.document_instance.domain, property)
        return super(IndicatorAdminCRUDManager, self).format_property(key, property)

    def create(self, **kwargs):
        namespace = kwargs['namespace']
        del kwargs['namespace']
        self.document_instance = self.document_class.increment_or_create_unique(namespace, self.domain, **kwargs)

    def update(self, **kwargs):
        # update and create behave the same here
        self.create(**kwargs)


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


class CaseDataInFormIndicatorAdminCRUDManager(BaseFormIndicatorAdminCRUDManager):

    @property
    def properties_in_row(self):
        original_props = super(CaseDataInFormIndicatorAdminCRUDManager, self).properties_in_row
        return original_props[:3] + ["case_property"] + original_props[-2:]


class FormDataInCaseAdminCRUDManager(BaseFormIndicatorAdminCRUDManager):

    @property
    def properties_in_row(self):
        original_props = super(FormDataInCaseAdminCRUDManager, self).properties_in_row
        return original_props[:2] + ["case_type", "xmlns", "question_id"] + original_props[-2:]


class BaseDynamicIndicatorCRUDManager(IndicatorAdminCRUDManager):

    @property
    def properties_in_row(self):
        original_props = super(BaseDynamicIndicatorCRUDManager, self).properties_in_row
        return original_props[:2] + ["title", "description"] + original_props[-2:]


class CouchIndicatorCRUDManager(BaseDynamicIndicatorCRUDManager):

    @property
    def properties_in_row(self):
        original_props = super(CouchIndicatorCRUDManager, self).properties_in_row
        return original_props[:4] + ["couch_view", "indicator_key", "startdate_shift"] + original_props[-2:]

    def format_property(self, key, property):
        if key == "startdate_shift":
            return mark_safe(render_to_string("indicators/partials/time_shift_summary.html", {
                "startdate_shift": self.document_instance.startdate_shift,
                "enddate_shift": self.document_instance.enddate_shift,
                "fixed_datespan_days": self.document_instance.fixed_datespan_days,
                "fixed_datespan_months": self.document_instance.fixed_datespan_months,
            }))
        if key == "indicator_key":
            return property or '<span class="label label-default">None</span>'
        return super(CouchIndicatorCRUDManager, self).format_property(key, property)


class CombinedCouchIndicatorCRUDManager(BaseDynamicIndicatorCRUDManager):

    @property
    def properties_in_row(self):
        original_props = super(CombinedCouchIndicatorCRUDManager, self).properties_in_row
        return original_props[:4] + ["numerator_slug", "denominator_slug"] + original_props[-2:]



