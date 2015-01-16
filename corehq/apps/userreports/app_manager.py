from corehq.apps.app_manager.util import ParentCasePropertyBuilder
from corehq.apps.app_manager.xform import XForm
from corehq.apps.userreports.models import DataSourceConfiguration
import unidecode


def get_case_data_sources(app):
    """
    Returns a dict mapping case types to DataSourceConfiguration objects that have
    the default set of case properties built in.
    """
    return {case_type: get_case_data_source(app, case_type) for case_type in app.get_case_types() if case_type}


def get_default_case_property_datatypes():
    return {
        "name": "string",
        "modified_on": "datetime",
        "opened_on": "datetime",
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
        table_id=_clean_table_name(app.domain, case_type),
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
            forms = {form.xmlns: get_form_data_source(app, form)}

    return forms


DATATYPE_MAP = {
    "Select": "single",
    "MSelect": "multiple"
}


def get_form_data_source(app, form):
    xform = XForm(form.source)
    form_name = form.default_name()

    def _get_indicator_data_type(data_type, options):
        if data_type == "date":
            return {"datatype": "date"}
        if data_type == "MSelect":
            return {
                "type": "choice_list",
                "select_style": DATATYPE_MAP[data_type],
                "choices": [
                    option['value'] for option in options
                ],
            }
        return {"datatype": "string"}

    def _make_indicator(question):
        path = question['value'].split('/')
        data_type = question['type']
        options = question.get('options')
        ret = {
            "type": "raw",
            "column_id": path[-1],
            'property_path': ['form'] + path[2:],
            "display_name": path[-1],
        }
        ret.update(_get_indicator_data_type(data_type, options))
        return ret

    def _make_meta_block_indicator(field_name, data_type):
        ret = {
            "type": "raw",
            "column_id": field_name,
            "property_path": ['form', 'meta'] + [field_name],
            "display_name": field_name,
        }
        ret.update(_get_indicator_data_type(data_type, []))
        return ret

    questions = xform.get_questions([])

    return DataSourceConfiguration(
        domain=app.domain,
        referenced_doc_type='XFormInstance',
        table_id=_clean_table_name(app.domain, form_name),
        display_name=form_name,
        configured_filter={
            "type": "property_match",
            "property_name": "xmlns",
            "property_path": [],
            "property_value": xform.data_node.tag_xmlns
        },
        configured_indicators=[
            _make_indicator(q) for q in questions
        ] + [
            _make_meta_block_indicator(field[0], field[1]) for field in [
                ('username', 'string'),
                ('userID', 'string'),
                ('timeStart', 'datetime'),
                ('timeEnd', 'datetime'),
                ('deviceID', 'string'),
            ]
        ],
    )


def _clean_table_name(domain, readable_name):
    """
    Slugifies and truncates readable name to make a valid configurable report table name.
    """
    name_slug = '_'.join(unidecode.unidecode(readable_name).lower().split(' '))
    # 63 = max postgres table name, 24 = table name prefix + hash overhead
    max_length = 63 - len(domain) - 24
    return name_slug[:max_length]
