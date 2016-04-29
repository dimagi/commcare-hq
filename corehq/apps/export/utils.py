from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.modules import to_function

from corehq.apps.reports.models import (
    FormExportSchema,
    CaseExportSchema,
)
from .const import (
    CASE_EXPORT,
    FORM_EXPORT,
    DEID_TRANSFORM_FUNCTIONS,
    TRANSFORM_FUNCTIONS,
)


def is_occurrence_deleted(last_occurrences, app_ids_and_versions):
    is_deleted = True
    for app_id, version in app_ids_and_versions.iteritems():
        if last_occurrences.get(app_id) == version:
            is_deleted = False
            break
    return is_deleted


def convert_saved_export_to_export_instance(domain, saved_export):
    from .models import (
        FormExportDataSchema,
        FormExportInstance,
        CaseExportDataSchema,
        CaseExportInstance,
        PathNode,
    )

    # Build a new schema and instance
    schema = None
    instance_cls = None
    export_type = saved_export.type
    if export_type == FORM_EXPORT:
        instance_cls = FormExportInstance
        schema = FormExportDataSchema.generate_schema_from_builds(
            domain,
            saved_export.app_id,
            _extract_xmlns_from_index(saved_export.index),
        )
    elif export_type == CASE_EXPORT:
        instance_cls = CaseExportInstance
        schema = CaseExportDataSchema.generate_schema_from_builds(
            domain,
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
            new_table.selected = True
        else:
            continue

        # The SavedExportSchema only saves selected columns so default all the selections to False
        # unless found in the SavedExportSchema (legacy)
        for new_column in new_table.columns:
            new_column.selected = False

        for column in old_table.columns:
            index = column.index
            transform = None  # can be either the deid_transform or the value transform on the ExportItem

            if column.doc_type == 'StockExportColumn':
                # Handle stock export column separately because it's a messy edge since
                # it doesn't have a unique index (_id).
                index, new_column = new_table.get_column(
                    [PathNode(name='stock')],
                    'ExportItem',
                    None,
                )
                if new_column:
                    new_column.selected = True
                    new_column.label = column.display
                continue

            if column.transform:
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

            system_property = _get_system_property(
                column.index,
                transform,
                export_type,
                new_table.path
            )
            if system_property:
                column_path, transform = system_property

            guess_types = ['ScalarItem', 'MultipleChoiceItem', 'ExportItem']
            # Since old exports had no concept of item type, we just guess all
            # the types and see if there are any matches.
            for guess_type in guess_types:
                index, new_column = new_table.get_column(
                    column_path,
                    guess_type,
                    _strip_deid_transform(transform),
                )
                if new_column:
                    break

            if not new_column:
                continue
            new_column.label = column.display
            new_column.selected = True
            if transform and not _strip_deid_transform(transform):
                # Must be deid transform
                new_column.deid_transform = transform

    instance.save()

    saved_export.doc_type += DELETED_SUFFIX
    saved_export.converted_saved_export_id = instance._id
    saved_export.save()

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


def _strip_deid_transform(transform):
    return None if transform in DEID_TRANSFORM_FUNCTIONS.keys() else transform


def _convert_transform(serializable_transform):
    transform_fn = to_function(serializable_transform.dumps_simple())
    if not transform_fn:
        return None
    for slug, fn in list(TRANSFORM_FUNCTIONS.iteritems()) + list(DEID_TRANSFORM_FUNCTIONS.iteritems()):
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
        PARENT_CASE_PROPERTY_MAPPING,
        REPEAT_GROUP_PROPERTY_MAPPING,
    )

    system_property = None
    transform = _strip_deid_transform(transform)
    if export_type == FORM_EXPORT:
        if table_path == MAIN_TABLE:
            system_property = FORM_PROPERTY_MAPPING.get((index, transform))
        elif table_path[-1].is_repeat:
            system_property = REPEAT_GROUP_PROPERTY_MAPPING.get((index, transform))
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


def revert_new_exports(new_exports):
    """
    Takes a list of new style ExportInstance and marks them as deleted as well as restoring
    the old export it was converted from (if it was converted from an old export)

    :param new_exports: List of ExportInstance
    :returns: Any old exports that were restored when decommissioning the new exports
    """
    reverted_exports = []
    for new_export in new_exports:
        if new_export.legacy_saved_export_schema_id:
            schema_cls = FormExportSchema if new_export.type == FORM_EXPORT else CaseExportSchema
            old_export = schema_cls.get(new_export.legacy_saved_export_schema_id)
            old_export.doc_type = old_export.doc_type.rstrip(DELETED_SUFFIX)
            old_export.save()
            reverted_exports.append(old_export)
        new_export.doc_type += DELETED_SUFFIX
        new_export.save()
    return reverted_exports
