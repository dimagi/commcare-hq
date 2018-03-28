from django.utils.translation import ugettext_lazy as _

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
