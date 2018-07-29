from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.indicators.admin import BaseIndicatorAdminInterface
from corehq.apps.indicators.admin.forms import (FormDataAliasIndicatorDefinitionForm,
                                                FormLabelIndicatorDefinitionForm, CaseDataInFormIndicatorDefinitionForm, FormDataInCaseForm)
from corehq.apps.indicators.models import (FormDataAliasIndicatorDefinition,
                                           FormLabelIndicatorDefinition, CaseDataInFormIndicatorDefinition, FormDataInCaseIndicatorDefinition)
from corehq.apps.reports.datatables import DataTablesColumn


class FormLabelIndicatorDefinitionAdminInterface(BaseIndicatorAdminInterface):
    name = FormLabelIndicatorDefinition.get_nice_name()
    description = "Maps a form_label to an XMLNS for that form."
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
    description = ("Maps a question id from that form to an indicator slug that can be referenced across all projects "
                   "in the indicator couch views.")
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
    description = ("Grabs the specified case property value of the form's related case and inserts it into the form's "
                   "indicators.")
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
    description = ("Takes the value from the question_id / data_node path specified from that case's related form(s)"
                   "---matched by XMLNS---and inserts it into that case's indicators.")
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
