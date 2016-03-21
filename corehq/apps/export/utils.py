from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.modules import to_function

from .const import TRANSFORM_FUNCTIONS, FORM_PROPERTY_MAPPING
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
    for old_table in saved_export.tables:
        table_path = _convert_index_to_path_nodes(old_table.index)
        new_table = instance.get_table(_convert_index_to_path_nodes(old_table.index))
        if new_table:
            new_table.label = old_table.display
        else:
            continue

        # The SavedExportSchema only saves selected columns so default all the selections to False
        # unless found in the SavedExportSchema (legacy)
        for new_column in new_table.columns:
            new_column.selected = False

        for column in old_table.columns:
            index = column.index
            transform = _convert_transform(column.transform)
            if _is_repeat(old_table.index):
                index = '{table_index}.{column_index}'.format(
                    table_index=_strip_repeat_index(old_table.index),
                    column_index=column.index,
                )
            column_path = _convert_index_to_path_nodes(index)
            # The old style column indexes always look like they contains no repeats,
            # so replace that parts that could be repeats with the table path
            column_path = table_path + column_path[len(table_path):]

            if _get_system_property(column.index, column.transform):
                index, transform = _get_system_property(column.index, column.transform)

            new_column = new_table.get_column(
                column_path,
                transform,
            )
            if not new_column:
                continue
            new_column.label = column.display
            new_column.selected = True
            if transform:
                new_column.transforms = [transform]

    saved_export.doc_type += DELETED_SUFFIX
    saved_export.save()
    instance.save()

    return instance


def _extract_xmlns_from_index(index):
    return index[1]


def _is_repeat(index):
    return index.startswith('#') and index.endswith('#') and index != '#'


def _strip_repeat_index(index):
    index = index.strip('#.')
    index = index.replace('#.', '')  # For nested repeats
    return index


def _convert_transform(serializable_transform):
    transform_fn = to_function(serializable_transform.dumps_simple())
    if not transform_fn:
        return None
    for slug, fn in TRANSFORM_FUNCTIONS.iteritems():
        if fn == transform_fn:
            return slug
    return None


def _convert_index_to_path(index):
    from corehq.apps.export.models.new import MAIN_TABLE
    if index == '#':
        return MAIN_TABLE
    elif _is_repeat(index):
        return _strip_repeat_index(index).split('.')
    else:
        return index.split('.')


def _get_system_property(index, transform):
    return FORM_PROPERTY_MAPPING.get((index, transform))


def _convert_index_to_path_nodes(index):
    from corehq.apps.export.models.new import MAIN_TABLE
    from corehq.apps.export.models.new import PathNode
    if index == '#':
        return MAIN_TABLE
    elif _is_repeat(index):
        split_index = index.split('.')[1:]  # Remove first "#"
        path = []

        for part in split_index:
            # If the part is "#" we know the previous piece in the path is a repeat group
            if part == '#':
                path[-1].is_repeat = True
            else:
                path.append(PathNode(name=part, is_repeat=False))
        return path
    else:
        return [PathNode(name=n) for n in index.split('.')]
