from text_unidecode import unidecode

from corehq.apps.app_manager.xform import XForm
from corehq.apps.export.models import (
    CaseExportDataSchema,
    CaseIndexItem,
    FormExportDataSchema,
)
from corehq.apps.export.system_properties import (
    BOTTOM_MAIN_FORM_TABLE_PROPERTIES,
    MAIN_CASE_TABLE_PROPERTIES,
)
from corehq.apps.userreports.app_manager.data_source_meta import (
    make_case_data_source_filter,
    make_form_data_source_filter,
)
from corehq.apps.userreports.exceptions import DuplicateColumnIdError
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.sql import get_column_name


def get_case_data_sources(app):
    """
    Returns a dict mapping case types to DataSourceConfiguration objects that have
    the default set of case properties built in.
    """
    return {case_type: get_case_data_source(app, case_type) for case_type in app.get_case_types() if case_type}


def get_case_data_source(app, case_type):
    schema = CaseExportDataSchema.generate_schema(
        app.domain,
        app._id,
        case_type,
        only_process_current_builds=True,
    )
    # the first two (row number and case id) are redundant/export specific,
    meta_properties_to_use = MAIN_CASE_TABLE_PROPERTIES[2:]
    # anything with a transform should also be removed
    meta_properties_to_use = [
        property_def
        for property_def in meta_properties_to_use
        if property_def.item.transform is None
    ]
    meta_indicators = [_export_column_to_ucr_indicator(c) for c in meta_properties_to_use]
    dynamic_indicators = _get_dynamic_indicators_from_export_schema(schema)
    # filter out any duplicately defined columns from dynamic indicators
    meta_column_names = set([c['column_id'] for c in meta_indicators])
    dynamic_indicators = [indicator for indicator in dynamic_indicators if
                          indicator['column_id'] not in meta_column_names]
    return DataSourceConfiguration(
        domain=app.domain,
        referenced_doc_type='CommCareCase',
        table_id=clean_table_name(app.domain, case_type),
        display_name=case_type,
        configured_filter=make_case_data_source_filter(case_type),
        configured_indicators=meta_indicators + dynamic_indicators + _get_shared_indicators(),
    )


def get_form_data_sources(app):
    """
    Returns a dict mapping forms to DataSourceConfiguration objects

    This is never used, except for testing that each form in an app will source correctly
    """
    forms = {}

    for module in app.get_modules():
        for form in module.get_forms():
            forms[form.xmlns] = get_form_data_source(app, form)

    return forms


def get_form_data_source(app, form):
    xform = XForm(form.source, domain=app.domain)
    schema = FormExportDataSchema.generate_schema(
        app.domain,
        app._id,
        xform.data_node.tag_xmlns,
        only_process_current_builds=True,
    )
    meta_properties = [
        _export_column_to_ucr_indicator(c) for c in BOTTOM_MAIN_FORM_TABLE_PROPERTIES
        if c.label != 'form_link'
    ]
    dynamic_properties = _get_dynamic_indicators_from_export_schema(schema)
    form_name = form.default_name()
    config = DataSourceConfiguration(
        domain=app.domain,
        referenced_doc_type='XFormInstance',
        table_id=clean_table_name(app.domain, form_name),
        display_name=form_name,
        configured_filter=make_form_data_source_filter(xform.data_node.tag_xmlns, app.get_id),
        configured_indicators=meta_properties + dynamic_properties + _get_shared_indicators(),
    )
    return _deduplicate_columns_if_necessary(config)


def _deduplicate_columns_if_necessary(config):
    try:
        config.validate()
    except DuplicateColumnIdError as e:
        # deduplicate any columns by adding a hash of the full display_name/path
        for indicator in config.configured_indicators:
            if indicator['column_id'] in e.columns:
                indicator['column_id'] = get_column_name(indicator['display_name'], add_hash=True)

        # clear indicators cache, which is awkward with properties
        DataSourceConfiguration.indicators.fget.reset_cache(config)
        config.validate()
    return config


def _get_shared_indicators():
    return [
        {
            "type": "expression",
            "column_id": 'count',
            "display_name": 'count',
            "datatype": 'small_integer',
            "expression": {
                "type": "constant",
                'constant': 1,
            }
        }
    ]


def _get_dynamic_indicators_from_export_schema(schema):
    main_schema = schema.group_schemas[0]
    return [_export_item_to_ucr_indicator(i) for i in main_schema.items]


def _export_column_to_ucr_indicator(export_column):
    """
    Converts an ExportColumn (from exports module) to a UCR indicator definition.
    :param export_column:
    :return: a dict ready to be inserted into a UCR data source
    """
    return {
        "type": "expression",
        "column_id": get_column_name(export_column.label, add_hash=False),
        "display_name": export_column.label,
        "datatype": export_column.item.datatype or 'string',
        "expression": {
            "type": "property_path",
            'property_path': [p.name for p in export_column.item.path],
        }
    }


def _export_item_to_ucr_indicator(export_item):
    """
    Converts an ExportItem (from exports module) to a UCR indicator definition.
    :param export_item:
    :return: a dict ready to be inserted into a UCR data source
    """
    if isinstance(export_item, CaseIndexItem):
        # dereference indices
        inner_expression = {
            "type": "nested",
            # this pulls out the entire CommCareCaseIndex object
            "argument_expression": {
                "type": "array_index",
                "array_expression": {
                    # filter indices down to those with the correct case type
                    "type": "filter_items",
                    "items_expression": {
                        "type": "property_name",
                        "property_name": "indices"
                    },
                    "filter_expression": {
                        "type": "boolean_expression",
                        "expression": {
                            "type": "property_name",
                            "property_name": "referenced_type"
                        },
                        "operator": "eq",
                        "property_value": export_item.case_type
                    }
                },
                # return the first (assumes only 0 or 1)
                "index_expression": {
                    "type": "constant",
                    "constant": 0
                }
            },
            # this pulls out the referenced case ID from the object
            "value_expression": {
                "type": "property_name",
                "property_name": "referenced_id"
            }
        }
    else:
        inner_expression = {
            "type": "property_path",
            'property_path': [p.name for p in export_item.path],
        }
    return {
        "type": "expression",
        "column_id": get_column_name(export_item.readable_path, add_hash=False),
        "display_name": export_item.readable_path,
        "datatype": export_item.datatype or 'string',
        "expression": inner_expression,
    }


def clean_table_name(domain, readable_name):
    """
    Slugifies and truncates readable name to make a valid configurable report table name.
    """
    name_slug = '_'.join(unidecode(readable_name).lower().split(' '))
    # 63 = max postgres table name, 24 = table name prefix + hash overhead
    max_length = 63 - len(domain) - 24
    return name_slug[:max_length]
