from dimagi.utils.couch.undo import DELETED_SUFFIX

from .const import TRANSFORM_FUNCTIONS, MAIN_TABLE
from .exceptions import ExportInvalidTransform


def is_valid_transform(value):
    for transform in value:
        if transform not in TRANSFORM_FUNCTIONS:
            raise ExportInvalidTransform('{} is not a valid transform'.format(value))


def convert_saved_export_to_export_instance(saved_export):
    from .models import FormExportDataSchema, FormExportInstance

    # Build a new schema and instance
    schema = FormExportDataSchema.generate_schema_from_builds(
        saved_export.domain,
        saved_export.app_id,
        _extract_xmlns_from_index(saved_export.index),
    )

    instance = FormExportInstance.generate_instance_from_schema(
        schema,
        schema.domain,
        schema.app_id
    )
    instance.name = saved_export.name
    instance.is_deidentified = saved_export.is_safe
    instance.export_format = saved_export.default_format
    instance.transform_dates = saved_export.transform_dates
    instance.split_multiselects = saved_export.split_multiselects
    instance.include_errors = saved_export.include_errors
    instance.legacy_saved_export_schema_id = saved_export._id

    # With new export instance, copy over preferences from previous export
    for table in saved_export.tables:
        new_table = instance.get_table(_convert_index_to_path(table.index))
        if new_table:
            new_table.display_name = table.display
        else:
            continue

        # The SavedExportSchema only saves selected columns so default all the selections to False
        # unless found in the SavedExportSchema (legacy)
        for new_column in new_table.columns:
            new_column.selected = False

        for column in table.columns:
            index = column.index
            if _is_repeat(table.index):
                index = '{table_index}.{column_index}'.format(
                    table_index=_strip_repeat_index(table.index),
                    column_index=column.index,
                )

            new_column = new_table.get_column(_convert_index_to_path(index))
            if not new_column:
                continue
            new_column.label = column.display
            new_column.selected = True

    saved_export.doc_type += DELETED_SUFFIX
    saved_export.save()
    instance.save()

    return instance


def _extract_xmlns_from_index(index):
    return index[1]


def _is_repeat(index):
    return index.startswith('#') and index.endswith('#') and index != '#'


def _strip_repeat_index(index):
    return index.strip('#.')


def _convert_index_to_path(index):
    if index == '#':
        return MAIN_TABLE
    elif _is_repeat(index):
        return ['data'] + _strip_repeat_index(index).split('.')[1:]
    else:
        return ['data'] + index.split('.')[1:]
