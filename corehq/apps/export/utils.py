from dimagi.utils.couch.undo import DELETED_SUFFIX

from .const import TRANSFORM_FUNCTIONS
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

    instance = FormExportInstance.generate_instance_from_schema(schema)
    instance.name = saved_export.name
    instance.is_deidentified = saved_export.is_safe
    instance.export_format = saved_export.default_format
    instance.transform_dates = saved_export.transform_dates
    instance.split_multiselects = saved_export.split_multiselects
    instance.include_errors = saved_export.include_errors
    instance.legacy_saved_export_schema_id = saved_export._id

    # With new export instance, copy over preferences from previous export
    for table in saved_export.tables:
        table_path = _convert_index_to_path_nodes(table.index)
        new_table = instance.get_table(table_path)
        if new_table:
            new_table.label = table.display
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
            column_path = _convert_index_to_path_nodes(index)
            # The old style column indexes always look like they contains no repeats,
            # so replace that parts that could be repeats with the table path
            column_path = table_path + column_path[len(table_path):]

            new_column = new_table.get_column(
                column_path,
                _convert_serializable_function_to_transform(column.transform)
            )
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


def _convert_index_to_path_nodes(index):
    from corehq.apps.export.models.new import MAIN_TABLE
    from corehq.apps.export.models.new import PathNode
    if index == '#':
        return MAIN_TABLE
    elif _is_repeat(index):
        return [PathNode(name='data')] + [
            PathNode(name=n, is_repeat=True)
            for n in _strip_repeat_index(index).split('.')[1:]
        ]
    else:
        return [PathNode(name='data')] + [PathNode(name=n) for n in index.split('.')[1:]]


def _convert_serializable_function_to_transform(serializable_function):
    if serializable_function is None:
        return []
    else:
        # TODO: Write this
        raise NotImplementedError
