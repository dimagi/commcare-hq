from django.utils.translation import ugettext_lazy as _

from corehq.apps.data_dictionary.models import CaseProperty
from corehq.apps.export.det.base import DETRow, DETTable, DETConfig
from corehq.apps.export.det.exceptions import DETConfigError
from corehq.apps.export.models import FormExportInstance, CaseExportInstance
from corehq.apps.userreports import datatypes

PROPERTIES_PREFIX = 'properties.'
ID_FIELD = 'id'
FORM_ID_SOURCE = 'form.meta.instanceID'
CASE_ID_SOURCE = 'case_id'

# maps Case fields to the API field names used in CommCareCaseResource
CASE_API_PATH_MAP = {
    'closed': 'closed',
    'date_closed': 'date_closed',
    'date_modified': 'date_modified',
    'external_id': 'properties.external_id',
    'opened_on': 'properties.date_opened',
    'owner_id': 'properties.owner_id',
    '_id': 'id',
    'name': 'properties.case_name',
    'opened_by': 'opened_by',
    'server_modified_on': 'server_date_modified',
    'server_opened_on': 'server_date_opened',
    'type': 'properties.case_type',
    'user_id': 'user_id',
}

MAP_VIA_STR2DATE = 'str2date'
MAP_VIA_STR2NUM = 'str2num'


class DefaultDETSchemaHelper(object):
    """
    Helper to do datatype transformations, etc. during schema generation
    """
    @staticmethod
    def transform_path(input_path):
        return input_path

    @staticmethod
    def get_map_via(export_item):
        return {
            datatypes.DATA_TYPE_DATETIME: MAP_VIA_STR2DATE,
            datatypes.DATA_TYPE_DATE: MAP_VIA_STR2DATE,
            datatypes.DATA_TYPE_INTEGER: MAP_VIA_STR2NUM,
            datatypes.DATA_TYPE_DECIMAL: MAP_VIA_STR2NUM,
        }.get(export_item.datatype, '')


class CaseDETSchemaHelper(DefaultDETSchemaHelper):
    """
    Schema helper for cases
    """
    def __init__(self, dd_property_types):
        self.dd_property_types = dd_property_types

    @staticmethod
    def transform_path(input_path):
        # either return hard-coded lookup or add prefix
        return CASE_API_PATH_MAP.get(input_path, f'{PROPERTIES_PREFIX}{input_path}')

    def get_map_via(self, export_item):
        explicit_type = super().get_map_via(export_item)
        if not explicit_type and export_item.readable_path in self.dd_property_types:
            return _dd_type_to_det_type(self.dd_property_types[export_item.readable_path])
        return explicit_type


class RepeatDETSchemaHelper(DefaultDETSchemaHelper):
    """
    Schema helper for form repeats
    """
    def __init__(self, base_path):
        self.base_path = base_path

    def transform_path(self, input_path):
        # for repeats strip the base path from the input path
        return input_path.replace(f'{self.base_path}.', '')


def generate_from_export_instance(export_instance, output_file):
    if isinstance(export_instance, CaseExportInstance):
        return generate_from_case_export_instance(export_instance, output_file)
    elif isinstance(export_instance, FormExportInstance):
        return generate_from_form_export_instance(export_instance, output_file)
    else:
        raise DETConfigError(_('Export instance type {name} not supported!').format(
            name=type(export_instance).__name__
        ))


def generate_from_case_export_instance(export_instance, output_file):
    assert isinstance(export_instance, CaseExportInstance)
    if not export_instance.selected_tables:
        raise DETConfigError(_('No Tables found in Export {name}').format(name=export_instance.name))
    main_input_table = export_instance.selected_tables[0]
    main_output_table = DETTable(
        name=main_input_table.label,
        source='case',
        filter_name='type',
        filter_value=export_instance.case_type,
        rows=[],
    )
    output = DETConfig(name=export_instance.name, tables=[main_output_table])

    dd_property_types_by_name = _get_dd_property_types(export_instance.domain, export_instance.case_type)
    helper = CaseDETSchemaHelper(dd_property_types=dd_property_types_by_name)
    _add_rows_for_table(main_input_table, main_output_table, helper=helper)
    _add_id_row_if_necessary(main_output_table, CASE_ID_SOURCE)
    # todo: add rows for other tables
    output.export_to_file(output_file)


def _get_dd_property_types(domain, case_type):
    """
    Get a dictionary of property types by name (from the data dictionary) for a given
    domain, case_type. e.g.
    {
      "name": "plain",
      "location": "gps",
      "event_date": "date",
    }
    """
    return dict(
        CaseProperty.objects.filter(
            case_type__domain=domain,
            case_type__name=case_type,
        ).values_list('name', 'data_type')
    )


def _dd_type_to_det_type(data_dictionary_datatype):
    return {
        'date': MAP_VIA_STR2DATE,
        'number': MAP_VIA_STR2NUM,
    }.get(data_dictionary_datatype, '')


def generate_from_form_export_instance(export_instance, output_file):
    assert isinstance(export_instance, FormExportInstance)
    if not export_instance.selected_tables:
        raise DETConfigError(_('No Tables found in Export {name}').format(name=export_instance.name))

    output = DETConfig(name=export_instance.name)
    for input_table in export_instance.selected_tables:
        if _is_main_form_table(input_table):
            output_table = DETTable(
                name=input_table.label,
                source='form',
                filter_name='xmlns',
                filter_value=export_instance.xmlns,
                rows=[],
            )
            _add_rows_for_table(input_table, output_table)
            _add_id_row_if_necessary(output_table, FORM_ID_SOURCE)
        else:
            output_table = DETTable(
                name=input_table.label,
                source=f'form.{input_table.readable_path}[*]',
                filter_name='xmlns',
                filter_value=export_instance.xmlns,
                rows=[],
            )

            helper = RepeatDETSchemaHelper(base_path=input_table.readable_path)
            _add_rows_for_table(input_table, output_table, helper=helper)

        output.tables.append(output_table)

    output.export_to_file(output_file)


def _is_main_form_table(table_configuration):
    return table_configuration.readable_path == ''


def _add_id_row_if_necessary(output_table, source_value):
    # DET requires an "id" field to exist to use SQL export.
    # Insert one at the beginning of the table if it doesn't exist.
    if not any(row.field == ID_FIELD for row in output_table.rows):
        output_table.rows.insert(0, DETRow(
            source_field=source_value,
            field=ID_FIELD,
        ))


def _add_rows_for_table(input_table, output_table, helper=None):
    if helper is None:
        helper = DefaultDETSchemaHelper()
    for column in input_table.selected_columns:
        det_row = _get_det_row_for_export_column(column, helper)
        output_table.rows.append(det_row)


def _get_det_row_for_export_column(column, helper):
    return DETRow(
        source_field=helper.transform_path(column.item.readable_path),
        field=column.label,
        map_via=helper.get_map_via(column.item)
    )
