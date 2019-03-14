from __future__ import absolute_import, unicode_literals
from abc import ABCMeta, abstractmethod
import six
from django.utils.translation import ugettext_lazy as _

from corehq.apps.app_manager.models import Form
from corehq.apps.app_manager.xform import XForm
from corehq.util.python_compatibility import soft_assert_type_text

DATA_SOURCE_TYPE_CASE = 'case'
DATA_SOURCE_TYPE_FORM = 'form'
DATA_SOURCE_TYPE_RAW = 'data_source'  # this is only used in report builder
APP_DATA_SOURCE_TYPE_VALUES = (DATA_SOURCE_TYPE_CASE, DATA_SOURCE_TYPE_FORM)
REPORT_BUILDER_DATA_SOURCE_TYPE_VALUES = (DATA_SOURCE_TYPE_CASE, DATA_SOURCE_TYPE_FORM, DATA_SOURCE_TYPE_RAW)
DATA_SOURCE_TYPE_CHOICES = (
    (DATA_SOURCE_TYPE_CASE, _("Cases")),
    (DATA_SOURCE_TYPE_FORM, _("Forms")),
)
DATA_SOURCE_DOC_TYPE_MAPPING = {
    DATA_SOURCE_TYPE_CASE: 'CommCareCase',
    DATA_SOURCE_TYPE_FORM: 'XFormInstance',
}


def get_data_source_doc_type(data_source_type):
    return DATA_SOURCE_DOC_TYPE_MAPPING[data_source_type]


def make_case_data_source_filter(case_type):
    return {
        "type": "boolean_expression",
        "operator": "eq",
        "expression": {
            "type": "property_name",
            "property_name": "type"
        },
        "property_value": case_type,
    }


def make_form_data_source_filter(xmlns, app_id):
    return {
        "type": "and",
        "filters": [
            {
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "xmlns"
                },
                "property_value": xmlns,
            },
            {
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "app_id"
                },
                "property_value": app_id,
            }
        ]
    }


def get_app_data_source_meta(domain, data_source_type, data_source_id):
    """
    Get an AppDataSourceMeta object based on the expected domain, source type and ID
    :param domain: the domain
    :param data_source_type: must be "form" or "case"
    :param data_source_id: for forms - the unique form ID, for cases the case type
    :return: an AppDataSourceMeta object corresponding to the data source type and ID
    """
    assert data_source_type in APP_DATA_SOURCE_TYPE_VALUES
    if data_source_type == DATA_SOURCE_TYPE_CASE:
        return CaseDataSourceMeta(domain, data_source_type, data_source_id)
    else:
        return FormDataSourceMeta(domain, data_source_type, data_source_id)


class AppDataSourceMeta(six.with_metaclass(ABCMeta, object)):
    """
    Utility base class for interacting with forms/cases inside an app and data sources
    """

    def __init__(self, domain, data_source_type, data_source_id):
        self.domain = domain
        self.data_source_type = data_source_type
        self.data_source_id = data_source_id

    def get_doc_type(self):
        return get_data_source_doc_type(self.data_source_type)

    @abstractmethod
    def get_filter(self):
        pass


class CaseDataSourceMeta(AppDataSourceMeta):

    def get_filter(self):
        return make_case_data_source_filter(self.data_source_id)


class FormDataSourceMeta(AppDataSourceMeta):

    def __init__(self, domain, data_source_type, data_source_id):
        super(FormDataSourceMeta, self).__init__(domain, data_source_type, data_source_id)
        self.source_form = Form.get_form(self.data_source_id)
        self.source_xform = XForm(self.source_form.source)

    def get_filter(self):
        return make_form_data_source_filter(
            self.source_xform.data_node.tag_xmlns, self.source_form.get_app().get_id)


def make_form_question_indicator(question, column_id=None, data_type=None, root_doc=False):
    """
    Return a data source indicator configuration (a dict) for the given form
    question.
    """
    path = question['value'].split('/')
    expression = {
        "type": "property_path",
        'property_path': ['form'] + path[2:],
    }
    if root_doc:
        expression = {"type": "root_doc", "expression": expression}
    return {
        "type": "expression",
        "column_id": column_id or question['value'],
        "display_name": path[-1],
        "datatype": data_type or get_form_indicator_data_type(question['type']),
        "expression": expression
    }


def get_form_indicator_data_type(question_type):
    return {
        "date": "date",
        "datetime": "datetime",
        "Date": "date",
        "DateTime": "datetime",
        "Int": "integer",
        "Double": "decimal",
        "Text": "string",
        "string": "string",
    }.get(question_type, "string")


def make_form_meta_block_indicator(spec, column_id=None, root_doc=False):
    """
    Return a data source indicator configuration (a dict) for the given
    form meta field and data type.
    """
    field_name = spec[0]
    if isinstance(field_name, six.string_types):
        soft_assert_type_text(field_name)
        field_name = [field_name]
    data_type = spec[1]
    column_id = column_id or field_name[0]
    expression = {
        "type": "property_path",
        "property_path": ['form', 'meta'] + field_name,
    }
    if root_doc:
        expression = {"type": "root_doc", "expression": expression}
    return {
        "type": "expression",
        "column_id": column_id,
        "display_name": field_name[0],
        "datatype": get_form_indicator_data_type(data_type),
        "expression": expression
    }
