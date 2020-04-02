from django.utils.translation import ugettext_lazy as _

from corehq.apps.export.det.base import DETRow, DETTable, DETConfig
from corehq.apps.export.det.exceptions import DETConfigError
from corehq.apps.export.models import FormExportInstance, CaseExportInstance

PROPERTIES_PREFIX = 'properties.'

# maps Case fields to the API field names used in CommCareCaseResource
CASE_API_PATH_MAP = {
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


def generate_from_export_instance(export_instance, output_file):
    if isinstance(export_instance, CaseExportInstance):
        return generate_from_case_export_instance(export_instance, output_file)
    elif isinstance(export_instance, FormExportInstance):
        return generate_from_form_export_instance(export_instance, output_file)
    else:
        raise DETConfigError(_(f'Export instance type {type(export_instance)} not supported!'))


def generate_from_case_export_instance(export_instance, output_file):
    assert isinstance(export_instance, CaseExportInstance)
    main_input_table = export_instance.selected_tables[0]
    main_output_table = DETTable(
        name=main_input_table.label,
        source='case',
        filter_name='type',
        filter_value=export_instance.case_type,
        rows=[],
    )
    output = DETConfig(name=export_instance.name, tables=[main_output_table])
    _add_rows_for_table(main_input_table, main_output_table, path_transform_fn=_transform_path_for_case_properties)
    # todo: add rows for other tables
    output.export_to_file(output_file)


def _transform_path_for_case_properties(input_path):
    # either return hard-coded lookup or add prefix
    return CASE_API_PATH_MAP.get(input_path, f'{PROPERTIES_PREFIX}{input_path}')


def generate_from_form_export_instance(export_instance, output_file):
    assert isinstance(export_instance, FormExportInstance)
    main_input_table = export_instance.selected_tables[0]
    main_output_table = DETTable(
        name=main_input_table.label,
        source='form',
        filter_name='xmlns',
        filter_value=export_instance.xmlns,
        rows=[],
    )
    output = DETConfig(name=export_instance.name, tables=[main_output_table])
    _add_rows_for_table(main_input_table, main_output_table)
    for additional_input_table in export_instance.selected_tables[1:]:
        additional_output_table = DETTable(
            name=additional_input_table.label,
            source=f'form.{additional_input_table.readable_path}[*]',
            filter_name='xmlns',
            filter_value=export_instance.xmlns,
            rows=[],
        )

        # note: this has to be defined here because it relies on closures
        def _strip_repeat_path(input_path):
            return input_path.replace(f'{additional_input_table.readable_path}.', '')

        _add_rows_for_table(additional_input_table, additional_output_table,
                            path_transform_fn=_strip_repeat_path)

        output.tables.append(additional_output_table)

    output.export_to_file(output_file)


def _add_rows_for_table(input_table, output_table, path_transform_fn=None):
    path_transform_fn = path_transform_fn if path_transform_fn else lambda x: x
    for column in input_table.selected_columns:
        det_row = _get_det_row_for_export_column(column, path_transform_fn)
        output_table.rows.append(det_row)


def _get_det_row_for_export_column(column, path_transform_fn):
    return DETRow(
        source_field=path_transform_fn(column.item.readable_path),
        field=column.label,
    )
