from corehq.apps.app_manager.util import ParentCasePropertyBuilder
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
