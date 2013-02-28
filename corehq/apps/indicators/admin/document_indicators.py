from corehq.apps.indicators.admin import BaseIndicatorAdminInterface
from corehq.apps.indicators.admin.forms import (FormDataAliasIndicatorDefinitionForm,
                                                FormLabelIndicatorDefinitionForm)
from corehq.apps.indicators.models import (FormDataAliasIndicatorDefinition,
                                           FormLabelIndicatorDefinition)
from corehq.apps.reports.datatables import DataTablesColumn


class FormLabelIndicatorDefinitionAdminInterface(BaseIndicatorAdminInterface):
    name = "Form Label Indicators"
    description = "desc needed"
    slug = "form_label"
    document_class = FormLabelIndicatorDefinition
    form_class = FormLabelIndicatorDefinitionForm

    @property
    def headers(self):
        header = super(FormLabelIndicatorDefinitionAdminInterface, self).headers
        header.insert_column(DataTablesColumn("XMLNS"), -3)
        return header


class FormAliasIndicatorDefinitionAdminInterface(BaseIndicatorAdminInterface):
    name = "Form Alias Indicators"
    description = "desc needed"
    slug = "form_alias"
    document_class = FormDataAliasIndicatorDefinition
    form_class = FormDataAliasIndicatorDefinitionForm

    @property
    def headers(self):
        header = super(FormAliasIndicatorDefinitionAdminInterface, self).headers
        header.insert_column(DataTablesColumn("XMLNS or Label"), -3)
        header.insert_column(DataTablesColumn("Question ID"), -3)
        return header

