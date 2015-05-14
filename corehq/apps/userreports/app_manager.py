from corehq.apps.app_manager.util import get_case_properties
from corehq.apps.app_manager.xform import XForm
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.reports.builder import (
    DEFAULT_CASE_PROPERTY_DATATYPES,
    FORM_METADATA_PROPERTIES,
    make_case_data_source_filter,
    make_case_property_indicator,
    make_form_data_source_filter,
    make_form_meta_block_indicator,
    make_form_question_indicator,
)
from corehq.apps.userreports.sql import get_column_name
import unidecode


def get_case_data_sources(app):
    """
    Returns a dict mapping case types to DataSourceConfiguration objects that have
    the default set of case properties built in.
    """
    return {case_type: get_case_data_source(app, case_type) for case_type in app.get_case_types() if case_type}


def get_case_data_source(app, case_type):

    prop_map = get_case_properties(app, [case_type], defaults=DEFAULT_CASE_PROPERTY_DATATYPES.keys())
    return DataSourceConfiguration(
        domain=app.domain,
        referenced_doc_type='CommCareCase',
        table_id=_clean_table_name(app.domain, case_type),
        display_name=case_type,
        configured_filter=make_case_data_source_filter(case_type),
        configured_indicators=[
            make_case_property_indicator(property) for property in prop_map[case_type]
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


def get_form_data_source(app, form):
    xform = XForm(form.source)
    form_name = form.default_name()
    questions = xform.get_questions([])

    return DataSourceConfiguration(
        domain=app.domain,
        referenced_doc_type='XFormInstance',
        table_id=_clean_table_name(app.domain, form_name),
        display_name=form_name,
        configured_filter=make_form_data_source_filter(xform.data_node.tag_xmlns),
        configured_indicators=[
            make_form_question_indicator(q, column_id=get_column_name(q['value']))
            for q in questions
        ] + [
            make_form_meta_block_indicator(field)
            for field in FORM_METADATA_PROPERTIES
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
