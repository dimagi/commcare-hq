from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.modules import to_function

from .const import (
    TRANSFORM_FUNCTIONS,
    CASE_EXPORT,
    FORM_EXPORT,
)
from .exceptions import ExportInvalidTransform


def is_valid_transform(value):
    for transform in value:
        if transform not in TRANSFORM_FUNCTIONS:
            raise ExportInvalidTransform('{} is not a valid transform'.format(value))


def convert_saved_export_to_export_instance(saved_export):
    from .models import (
        FormExportDataSchema,
        FormExportInstance,
        CaseExportDataSchema,
        CaseExportInstance,
    )

    # Build a new schema and instance
    schema = None
    instance_cls = None
    export_type = saved_export.type
    if export_type == FORM_EXPORT:
        instance_cls = FormExportInstance
        schema = FormExportDataSchema.generate_schema_from_builds(
            saved_export.domain,
            saved_export.app_id,
            _extract_xmlns_from_index(saved_export.index),
        )
    elif export_type == CASE_EXPORT:
        instance_cls = CaseExportInstance
        schema = CaseExportDataSchema.generate_schema_from_builds(
            saved_export.domain,
            _extract_casetype_from_index(saved_export.index),
        )

    instance = instance_cls.generate_instance_from_schema(schema)
    instance.name = saved_export.name
    instance.is_deidentified = saved_export.is_safe
    instance.export_format = saved_export.default_format
    instance.transform_dates = saved_export.transform_dates
    instance.legacy_saved_export_schema_id = saved_export._id
    if saved_export.type == FORM_EXPORT:
        instance.split_multiselects = saved_export.split_multiselects
        instance.include_errors = saved_export.include_errors

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
            transforms = []

            if column.transform:
                transforms = [_convert_transform(column.transform)]

            if _is_repeat(old_table.index):
                index = '{table_index}.{column_index}'.format(
                    table_index=_strip_repeat_index(old_table.index),
                    column_index=column.index,
                )
            column_path = _convert_index_to_path_nodes(index)
            # The old style column indexes always look like they contains no repeats,
            # so replace that parts that could be repeats with the table path
            column_path = table_path + column_path[len(table_path):]

            system_property = _get_system_property(
                column.index,
                _convert_transform(column.transform) if column.transform else None,
                export_type,
                new_table.path
            )
            if system_property:
                column_path, transform = system_property
                transforms = [transform] if transform else []

            new_column = new_table.get_column(
                column_path,
                transforms,
            )
            if not new_column:
                continue
            new_column.label = column.display
            new_column.selected = True
            if transforms:
                new_column.transforms = transforms

    saved_export.doc_type += DELETED_SUFFIX
    saved_export.save()
    instance.save()

    return instance


def _extract_xmlns_from_index(index):
    return index[1]


def _extract_casetype_from_index(index):
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


def _get_system_property(index, transform, export_type, table_path):
    from .models import (
        MAIN_TABLE,
        CASE_HISTORY_TABLE,
        PARENT_CASE_TABLE,
    )
    from .conversion_mappings import (
        FORM_PROPERTY_MAPPING,
        CASE_PROPERTY_MAPPING,
        CASE_HISTORY_PROPERTY_MAPPING,
        PARENT_CASE_PROPERTY_MAPPING
    )

    system_property = None
    if export_type == FORM_EXPORT:
        if table_path == MAIN_TABLE:
            system_property = FORM_PROPERTY_MAPPING.get((index, transform))
    elif export_type == CASE_EXPORT:
        if table_path == MAIN_TABLE:
            system_property = CASE_PROPERTY_MAPPING.get((index, transform))
        elif table_path == CASE_HISTORY_TABLE:
            system_property = CASE_HISTORY_PROPERTY_MAPPING.get((index, transform))
        elif table_path == PARENT_CASE_TABLE:
            system_property = PARENT_CASE_PROPERTY_MAPPING.get((index, transform))

    return system_property


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
