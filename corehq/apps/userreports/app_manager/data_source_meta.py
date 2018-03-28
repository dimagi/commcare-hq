from __future__ import absolute_import, unicode_literals
from abc import ABCMeta, abstractmethod
import six
from django.utils.translation import ugettext_lazy as _

from corehq.apps.app_manager.models import Form
from corehq.apps.app_manager.xform import XForm


DATA_SOURCE_TYPE_CASE = 'case'
DATA_SOURCE_TYPE_FORM = 'form'
DATA_SOURCE_TYPE_VALUES = (DATA_SOURCE_TYPE_CASE, DATA_SOURCE_TYPE_FORM)
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


def make_form_data_source_filter(xmlns):
    return {
        "type": "boolean_expression",
        "operator": "eq",
        "expression": {
            "type": "property_name",
            "property_name": "xmlns"
        },
        "property_value": xmlns,
    }


def get_app_data_source_meta(domain, data_source_type, data_source_id):
    """
    Get an AppDataSourceMeta object based on the expected domain, source type and ID
    :param domain: the domain
    :param data_source_type: must be "form" or "case"
    :param data_source_id: for forms - the unique form ID, for cases the case type
    :return: an AppDataSourceMeta object corresponding to the data source type and ID
    """
    assert data_source_type in DATA_SOURCE_TYPE_VALUES
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
        return make_case_data_source_filter


class CaseDataSourceMeta(AppDataSourceMeta):

    def get_filter(self):
        return make_case_data_source_filter(self.data_source_id)


class FormDataSourceMeta(AppDataSourceMeta):

    def __init__(self, domain, data_source_type, data_source_id):
        super(FormDataSourceMeta, self).__init__(domain, data_source_type, data_source_id)
        self.source_form = Form.get_form(self.data_source_id)
        self.source_xform = XForm(self.source_form.source)

    def get_filter(self):
        return make_form_data_source_filter(self.source_xform.data_node.tag_xmlns)
