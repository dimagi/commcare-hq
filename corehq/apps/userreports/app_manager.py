from corehq.apps.app_manager.util import ParentCasePropertyBuilder
from corehq.apps.app_manager.xform import XForm
from corehq.apps.userreports.models import DataSourceConfiguration


def get_case_data_sources(app):
    """
    Returns a dict mapping case types to DataSourceConfiguration objects that have
    the default set of case properties built in.
    """
    return {case_type: get_case_data_source(app, case_type) for case_type in app.get_case_types() if case_type}


def get_default_case_property_datatypes():
    return {
        "name": "string",
        "modified_on": "date",
        "opened_on": "date",
        "owner_id": "string",
        "user_id": "string",
    }


def get_case_data_source(app, case_type):
    default_case_property_datatypes = get_default_case_property_datatypes()
    def _make_indicator(property_name):
        return {
            "type": "raw",
            "column_id": property_name,
            "datatype": default_case_property_datatypes.get(property_name, "string"),
            'property_name': property_name,
            "display_name": property_name,
        }

    property_builder = ParentCasePropertyBuilder(app, default_case_property_datatypes.keys())
    return DataSourceConfiguration(
        domain=app.domain,
        referenced_doc_type='CommCareCase',
        table_id=case_type,
        display_name=case_type,
        configured_filter={
            'type': 'property_match',
            'property_name': 'type',
            'property_value': case_type,
        },
        configured_indicators=[
            _make_indicator(property) for property in property_builder.get_properties(case_type)
        ]
    )


def get_form_data_sources(app):
    """
    Returns a dict mapping forms to DataSourceConfiguration objects

    This is never used, except for testing that each form in an app will source correctly
    """
    forms = {}

    for module in app.modules:
        for form in module.forms:
            xform = XForm(form.source)
            langs = xform.get_languages()
            form_name = form.default_name()
            forms = {form_name: get_form_data_source(app, form)}

    return forms

DATATYPE_MAP = {
    "Select": "single",
    "MSelect": "multiple"
}


def get_form_data_source(app, form):
    xform = XForm(form.source)
    form_name = form.default_name()
    def _get_indicator_data_type(data_type, options):
        if data_type is "date":
            return {"datatype": "date"}
        if data_type in ("Select", "MSelect"):
            return {
                "type": "choice_list",
                "select_style": DATATYPE_MAP[data_type],
                "choices": [
                    option['value'] for option in options
                ],
            }
        return {"datatype": "string"}

    def _make_indicator(question):
        value = question['value'].split('/')[-1]  # /data/question_name -> question_name
        data_type = question['type']
        options = question.get('options')

        ret = {
            "type": "raw",
            "column_id": value,
            'property_name': value,
            "display_name": value,
        }
        ret.update(_get_indicator_data_type(data_type,options))
        return ret

    langs = xform.get_languages()
    questions = xform.get_questions(langs) # questions map to columns (indicators)

    return DataSourceConfiguration(
        domain=app.domain,
        referenced_doc_type='Form',
        table_id=form_name,
        display_name=form_name,
        configured_indicators=[
            _make_indicator(q) for q in questions
        ]
    )
