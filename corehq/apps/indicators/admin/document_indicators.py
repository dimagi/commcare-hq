from corehq.apps.indicators.admin import BaseIndicatorAdminInterface
from corehq.apps.indicators.admin.forms import (FormDataAliasIndicatorDefinitionForm,
                                                FormLabelIndicatorDefinitionForm, CaseDataInFormIndicatorDefinitionForm, FormDataInCaseForm)
from corehq.apps.indicators.models import (FormDataAliasIndicatorDefinition,
                                           FormLabelIndicatorDefinition, CaseDataInFormIndicatorDefinition, FormDataInCaseIndicatorDefinition)
from corehq.apps.reports.datatables import DataTablesColumn


class FormLabelIndicatorDefinitionAdminInterface(BaseIndicatorAdminInterface):
    name = FormLabelIndicatorDefinition.get_nice_name()
    description = "desc needed" #todo
    slug = "form_label"
    document_class = FormLabelIndicatorDefinition
    form_class = FormLabelIndicatorDefinitionForm

    @property
    def headers(self):
        header = super(FormLabelIndicatorDefinitionAdminInterface, self).headers
        header.insert_column(DataTablesColumn("XMLNS"), -3)
        return header


class FormAliasIndicatorDefinitionAdminInterface(BaseIndicatorAdminInterface):
    name = FormDataAliasIndicatorDefinition.get_nice_name()
    description = "desc needed" #todo
    slug = "form_alias"
    document_class = FormDataAliasIndicatorDefinition
    form_class = FormDataAliasIndicatorDefinitionForm

    @property
    def headers(self):
        header = super(FormAliasIndicatorDefinitionAdminInterface, self).headers
        header.insert_column(DataTablesColumn("XMLNS or Label"), -3)
        header.insert_column(DataTablesColumn("Question ID"), -3)
        return header


class CaseDataInFormAdminInterface(BaseIndicatorAdminInterface):
    name = CaseDataInFormIndicatorDefinition.get_nice_name()
    description = "" #todo
    slug = "form_case_data"
    document_class = CaseDataInFormIndicatorDefinition
    form_class = CaseDataInFormIndicatorDefinitionForm

    @property
    def headers(self):
        header = super(CaseDataInFormAdminInterface, self).headers
        header.insert_column(DataTablesColumn("XMLNS or Label"), -3)
        header.insert_column(DataTablesColumn("Case Property"), -3)
        return header


class FormDataInCaseAdminInterface(BaseIndicatorAdminInterface):
    name = FormDataInCaseIndicatorDefinition.get_nice_name()
    description = "todo" #todo
    slug = "case_form_data"
    document_class = FormDataInCaseIndicatorDefinition
    form_class = FormDataInCaseForm

    @property
    def headers(self):
        header = super(FormDataInCaseAdminInterface, self).headers
        header.insert_column(DataTablesColumn("Case Type"), -3)
        header.insert_column(DataTablesColumn("XMLNS or Label"), -3)
        header.insert_column(DataTablesColumn("Question ID"), -3)
        return header
