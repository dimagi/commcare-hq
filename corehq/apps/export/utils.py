from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.modules import to_function
from dimagi.utils.couch import CriticalSection
from toggle.shortcuts import set_toggle

from corehq.apps.accounting.utils import domain_has_privilege
from corehq.toggles import OLD_EXPORTS, NAMESPACE_DOMAIN, ALLOW_USER_DEFINED_EXPORT_COLUMNS
from corehq.util.log import with_progress_bar
from corehq.apps.hqwebapp.templatetags.hq_shared_tags import toggle_js_domain_cachebuster
from corehq.apps.reports.dbaccessors import (
    get_exports_json,
    stale_get_export_count,
)
from corehq.apps.reports.models import (
    FormExportSchema,
    CaseExportSchema,
    HQGroupExportConfiguration,
)
from corehq.apps.app_manager.const import STOCK_QUESTION_TAG_NAMES
from corehq.apps.app_manager.dbaccessors import (
    get_app,
    get_brief_apps_in_domain,
    get_apps_in_domain,
)
from .dbaccessors import (
    get_form_export_instances,
    get_case_export_instances,
    get_case_inferred_schema,
    get_form_inferred_schema,
)
from .exceptions import SkipConversion
from .const import (
    CASE_EXPORT,
    FORM_EXPORT,
    DEID_TRANSFORM_FUNCTIONS,
    TRANSFORM_FUNCTIONS,
    SKIPPABLE_PROPERTIES,
)

from corehq.privileges import EXCEL_DASHBOARD, DAILY_SAVED_EXPORT
import six


def is_occurrence_deleted(last_occurrences, app_ids_and_versions):
    is_deleted = True
    for app_id, version in six.iteritems(app_ids_and_versions):
        if last_occurrences.get(app_id) >= version:
            is_deleted = False
            break
    return is_deleted


def convert_saved_export_to_export_instance(
        domain,
        saved_export,
        force_convert_columns=False,
        dryrun=False):
    from .models import (
        FormExportDataSchema,
        FormExportInstance,
        CaseExportDataSchema,
        CaseExportInstance,
        ExportMigrationMeta,
        ConversionMeta,
        TableConfiguration,
        CaseInferredSchema,
        FormInferredSchema,
    )

    schema = None
    instance_cls = None
    export_type = saved_export.type

    daily_saved_export_ids = _get_daily_saved_export_ids(domain)

    is_remote_app_migration = _is_remote_app_conversion(
        domain,
        getattr(saved_export, 'app_id', None),
        export_type,
    )

    # Build a new schema and instance
    if export_type == FORM_EXPORT:
        xmlns = _extract_xmlns_from_index(saved_export.index)
        if not hasattr(saved_export, 'app_id'):
            # attempt to find app id from xmlns
            app_id = _app_id_from_xmlns(domain, xmlns)
        else:
            app_id = saved_export.app_id

        instance_cls = FormExportInstance
        schema = FormExportDataSchema.generate_schema_from_builds(
            domain,
            app_id,
            xmlns,
        )
    elif export_type == CASE_EXPORT:
        instance_cls = CaseExportInstance
        schema = CaseExportDataSchema.generate_schema_from_builds(
            domain,
            None,
            _extract_casetype_from_index(saved_export.index),
        )

    migration_meta = ExportMigrationMeta(
        saved_export_id=saved_export._id,
        domain=domain,
        export_type=export_type,
        is_remote_app_migration=is_remote_app_migration,
        migration_date=datetime.utcnow(),
        generated_schema_id=schema._id,
    )

    instance = instance_cls.generate_instance_from_schema(schema)
    instance.name = saved_export.name
    instance.is_deidentified = saved_export.is_safe
    instance.export_format = saved_export.default_format
    instance.transform_dates = getattr(saved_export, 'transform_dates', False)
    instance.legacy_saved_export_schema_id = saved_export._id
    instance.is_daily_saved_export = saved_export._id in daily_saved_export_ids
    if saved_export.type == FORM_EXPORT:
        instance.split_multiselects = getattr(saved_export, 'split_multiselects', False)
        instance.include_errors = getattr(saved_export, 'include_errors', False)

    inferred_schema = None

    # The SavedExportSchema only saves selected columns so default all the
    # selections to False unless found in the SavedExportSchema (legacy)
    for table in instance.tables:
        table.selected = False
        for column in table.columns:
            column.selected = False

    # With new export instance, copy over preferences from previous export
    for old_table in saved_export.tables:
        table_path = _convert_index_to_path_nodes(old_table.index)
        new_table = instance.get_table(_convert_index_to_path_nodes(old_table.index))
        if not new_table:
            if not is_remote_app_migration and not force_convert_columns:
                if old_table.index != '#.history.#':
                    migration_meta.skipped_tables.append(ConversionMeta(
                        path=old_table.index,
                        failure_reason='Not found in new export',
                    ))
                continue

            # Create a user defined TableConfiguration
            new_table = TableConfiguration(
                path=_convert_index_to_path_nodes(old_table.index),
            )
            instance._insert_system_properties(domain, instance.type, new_table)
            instance.tables.append(new_table)

        new_table.label = old_table.display
        new_table.selected = True
        migration_meta.converted_tables.append(ConversionMeta(
            path=old_table.index,
        ))

        # This keeps track of the order the columns should be in so we can reorder after
        # iterating over all the columns
        ordering = []

        for column in old_table.columns:
            info = []
            index = column.index
            transform = None  # can be either the deid_transform or the value transform on the ExportItem

            try:
                if column.doc_type == 'StockExportColumn':
                    # Form exports shouldn't export the Stock column, but there's
                    # a bug that lets users add it in old exports.
                    if saved_export.type == FORM_EXPORT:
                        continue
                    info.append('Column is a stock column')
                    _convert_stock_column(new_table, column)
                    continue

                if column.transform:
                    transform = _convert_transform(column.transform)
                    info.append('Column has a transform {} converted to {}'.format(
                        column.transform,
                        transform,
                    ))

                if _is_repeat(old_table.index):
                    index = '{table_index}.{column_index}'.format(
                        table_index=_strip_repeat_index(old_table.index),
                        column_index=column.index,
                    )
                    info.append('Column is part of a repeat: {}'. format(old_table.index))

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
                    info.append('Column is a system property. Path: {}. Transform: {}'.format(
                        column_path,
                        transform,
                    ))

                new_column = _get_normal_column(new_table, column_path, transform)

                # If we can't find the column in the current table
                # look in every other table to see if the column is a repeat
                # that did not receive more than one entry
                if not new_column:
                    new_column = _get_for_single_node_repeat(instance.tables, column_path, transform)
                    if new_column:
                        info.append('Column is for a repeat with just a single instance')

                # If we still haven't found the column, try to find it as a stock question
                if not new_column and _is_form_stock_question(index):
                    new_column = _get_column_for_stock_form_export(
                        new_table,
                        column_path,
                        index
                    )
                    if new_column:
                        info.append('Column is a stock form question')

                if not new_column:
                    raise SkipConversion('Column not found in new schema')
                else:
                    info.append('Column is guessed to be of type: {}'.format(
                        new_column.item.doc_type,
                    ))

                new_column.label = column.display
                new_column.selected = True
                if transform and not _strip_deid_transform(transform):
                    # Must be deid transform
                    new_column.deid_transform = transform
                    info.append('Column has deid_transform: {}'.format(transform))
                ordering.append(new_column)
            except SkipConversion as e:
                if is_remote_app_migration or force_convert_columns or column.index in SKIPPABLE_PROPERTIES:
                    # In the event that we skip a column and it's a remote application,
                    # add it to the inferred schema

                    schema_kwargs = {
                        'domain': domain
                    }
                    if not inferred_schema:
                        if instance.type == CASE_EXPORT:
                            inferred_schema = get_case_inferred_schema(domain, instance.identifier)
                            inferred_schema_cls = CaseInferredSchema
                            schema_kwargs['case_type'] = instance.identifier
                        elif instance.type == FORM_EXPORT:
                            inferred_schema = get_form_inferred_schema(
                                domain,
                                instance.app_id,
                                instance.identifier
                            )
                            inferred_schema_cls = FormInferredSchema
                            schema_kwargs['xmlns'] = instance.identifier
                            schema_kwargs['app_id'] = instance.app_id

                        if not inferred_schema:
                            inferred_schema = inferred_schema_cls(**schema_kwargs)

                    new_column = _create_column_from_inferred_schema(
                        inferred_schema,
                        new_table,
                        column,
                        column_path,
                        transform,
                    )

                    new_table.columns.append(new_column)
                    ordering.append(new_column)
                else:
                    migration_meta.skipped_columns.append(ConversionMeta(
                        path=column.index,
                        failure_reason=str(e),
                        info=info,
                    ))
            else:
                migration_meta.converted_columns.append(ConversionMeta(
                    path=column.index,
                    failure_reason=None,
                    info=info,
                ))

        new_table.columns = _reorder_columns(new_table, ordering)

    if not dryrun:
        migration_meta.save()
        instance.save()
        if inferred_schema:
            inferred_schema.save()

        saved_export.doc_type += DELETED_SUFFIX
        saved_export.converted_saved_export_id = instance._id
        saved_export.save()

    return instance, migration_meta


def _get_daily_saved_export_ids(domain):
    group_config = HQGroupExportConfiguration.get_for_domain(domain)
    return set(group_config.custom_export_ids)


def _extract_xmlns_from_index(index):
    return index[1]


def _extract_casetype_from_index(index):
    return index[1]


def _is_repeat(index):
    return index.startswith('#') and index.endswith('#') and index != '#'


def _create_column_from_inferred_schema(inferred_schema, new_table, old_column, column_path, transform):
    from .models import ExportColumn

    group_schema = inferred_schema.put_group_schema(new_table.path)
    item = group_schema.put_item(column_path, inferred_from='Export Migration')
    return ExportColumn(
        item=item,
        label=old_column.display,
        selected=True,
        deid_transform=transform,
    )


def _create_user_defined_column(old_column, column_path, transform):
    from .models import UserDefinedExportColumn

    column = UserDefinedExportColumn(
        label=old_column.display,
        selected=True,
        deid_transform=transform,
        custom_path=column_path,
        is_editable=False,
    )
    return column


def _app_id_from_xmlns(domain, xmlns):
    apps = get_apps_in_domain(domain)
    for app in apps:
        if hasattr(app, 'get_xmlns_map') and xmlns in app.get_xmlns_map():
            return app._id
    return None


def _strip_repeat_index(index):
    index = index.strip('#.')
    index = index.replace('#.', '')  # For nested repeats
    return index


def _reorder_columns(new_table, columns):
    """
    Given a TableConfiguration and a list of in order columns, this function
    returns a new list of columns that are in order based on the columns given.
    Any columns found in the table that aren't in the order are put after the
    ordered columns.
    """
    new_order = []
    for column in columns:
        new_order.append(column)
    for column in new_table.columns:
        if column not in new_order:
            new_order.append(column)
    return new_order


def _strip_deid_transform(transform):
    return None if transform in DEID_TRANSFORM_FUNCTIONS else transform


def _convert_transform(serializable_transform):
    transform_fn = to_function(serializable_transform.dumps_simple())
    if not transform_fn:
        return None
    for slug, fn in list(six.iteritems(TRANSFORM_FUNCTIONS)) + list(six.iteritems(DEID_TRANSFORM_FUNCTIONS)):
        if fn == transform_fn:
            return slug
    return None


def _get_for_single_node_repeat(tables, column_path, transform):
    """
    This function takes a column path and looks for it in all the other tables
    """
    from .models import MAIN_TABLE

    column_dot_path = '.'.join([node.name for node in column_path])
    for new_table in tables:
        if new_table.path == MAIN_TABLE:
            continue

        table_dot_path = '.'.join([node.name for node in new_table.path])
        if column_dot_path.startswith(table_dot_path + '.'):
            new_column_path = new_table.path + column_path[len(new_table.path):]
        else:
            continue
        new_column = _get_normal_column(new_table, new_column_path, transform)
        if new_column:
            return new_column


def _get_column_for_stock_form_export(new_table, column_path, index):
    # Takes a path like column.transfer:question_id.@date
    # and maps it to column.transfer.@date
    def _remove_question_id_from_path(path):
        parts = path.split('.')
        parts_without_question_ids = [part.split(':')[0] for part in parts]
        return '.'.join(parts_without_question_ids)

    stock_columns = [c for c in new_table.columns if c.item.doc_type == 'StockItem']

    # Map column to its readable path (dot path)
    stock_column_to_readable_path = {c: c.item.readable_path for c in stock_columns}

    matched_columns = []
    for column, readable_path in six.iteritems(stock_column_to_readable_path):
        if _remove_question_id_from_path(readable_path) == index:
            matched_columns.append(column)

    if len(matched_columns) == 1:
        return matched_columns[0]
    elif len(matched_columns) == 0:
        return None
    else:
        raise SkipConversion('Multiple matched stock nodes')


def _is_form_stock_question(index):
    parts = index.split('.')
    parent_stock_attributes = ['@date', '@type', '@entity-id', '@section-id']
    entry_stock_attributes = ['@id', '@quantity']

    # Attempts to take a balance node and convert it. It is looks for an index that matches:
    # <balance|transfer>.<@date|@type...>
    try:
        parent_tag_name, attribute = parts[-2:]
        if (parent_tag_name in STOCK_QUESTION_TAG_NAMES and
                attribute in parent_stock_attributes):
            return True
    except ValueError:
        return False

    # Attempts to take an entry node and convert it. It is looks for an index that matches:
    # <balance|transfer>.entry.<@id|@quantity>
    try:
        parent_tag_name, tag_name, attribute = parts[-3:]
        if (parent_tag_name in STOCK_QUESTION_TAG_NAMES and
                tag_name == 'entry' and
                attribute in entry_stock_attributes):
            return True
    except ValueError:
        return False

    return False


def _get_system_property(index, transform, export_type, table_path):
    """
    Given an old style export index and a transform, returns new style list of PathNodes
    and transform
    """
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
                if part != '#text':
                    path.append(PathNode(name=part, is_repeat=False))
        return path
    else:
        return [PathNode(name=n) for n in index.split('.')]


def _convert_stock_column(new_table, old_column):
    from .models import PathNode
    # Handle stock export column separately because it's a messy edge since
    # it doesn't have a unique index (_id).

    index, new_column = new_table.get_column(
        [PathNode(name='stock')],
        'ExportItem',
        None,
    )
    if new_column:
        new_column.selected = True
        new_column.label = old_column.display
    else:
        raise SkipConversion('StockExportColumn not found in new export')


def _get_normal_column(new_table, column_path, transform):
    guess_types = [
        'ScalarItem',
        'MultipleChoiceItem',
        'GeopointItem',
        'MultiMediaItem',
        'LabelItem',
        'ExportItem',
    ]

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
    return new_column


def _is_remote_app_conversion(domain, app_id, export_type):
    if app_id and export_type == FORM_EXPORT:
        app = get_app(domain, app_id)
        return app.is_remote_app()
    elif export_type == CASE_EXPORT:
        apps = get_brief_apps_in_domain(domain, include_remote=True)
        return any([app.is_remote_app() for app in apps])


def revert_new_exports(new_exports, dryrun=False):
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
            if not dryrun:
                old_export.save()
            reverted_exports.append(old_export)
        new_export.doc_type += DELETED_SUFFIX
        if not dryrun:
            new_export.save()
    return reverted_exports


def revert_migrate_domain(domain, dryrun=False):
    instances = get_form_export_instances(domain)
    instances.extend(get_case_export_instances(domain))

    reverted_exports = revert_new_exports(instances, dryrun=dryrun)

    if not dryrun:
        set_toggle(OLD_EXPORTS.slug, domain, True, namespace=NAMESPACE_DOMAIN)
        toggle_js_domain_cachebuster.clear(domain)

    for reverted_export in reverted_exports:
        print('Reverted export: {}'.format(reverted_export._id))


def migrate_domain(domain, dryrun=False, force_convert_columns=False):
    from couchexport.models import SavedExportSchema
    export_count = stale_get_export_count(domain)
    metas = []
    if export_count:
        for old_export in with_progress_bar(
                get_exports_json(domain),
                length=export_count,
                prefix=domain):
            with CriticalSection(['saved-export-{}'.format(old_export['_id'])], timeout=120):
                try:
                    _, migration_meta = convert_saved_export_to_export_instance(
                        domain,
                        SavedExportSchema.get(old_export['_id']),
                        dryrun=dryrun,
                        force_convert_columns=force_convert_columns,
                    )
                except Exception as e:
                    print('Failed parsing {}: {}'.format(old_export['_id'], e))
                    raise
                else:
                    metas.append(migration_meta)

    if not dryrun:
        set_toggle(OLD_EXPORTS.slug, domain, False, namespace=NAMESPACE_DOMAIN)
        toggle_js_domain_cachebuster.clear(domain)

    # Remote app migrations must have access to UserDefined columns and tables
    if any([meta.is_remote_app_migration for meta in metas]):
        set_toggle(
            ALLOW_USER_DEFINED_EXPORT_COLUMNS.slug,
            domain,
            True,
            namespace=NAMESPACE_DOMAIN
        )
        toggle_js_domain_cachebuster.clear(domain)

    for meta in metas:
        if not meta.skipped_tables and not meta.skipped_columns:
            continue

        output = '* Export information for export: {} *'.format(meta.old_export_url)
        schema_id_output = 'Generated schema: {}'.format(meta.generated_schema_id)
        print('')
        print('*' * len(output))
        print(output)
        print('* {}{} *'.format(schema_id_output, ' ' * (len(output) - len(schema_id_output) - 4)))
        print('*' * len(output))
        print('')

        if meta.skipped_tables:
            print('# Skipped tables #')
            for table_meta in meta.skipped_tables:
                table_meta.pretty_print()

        if meta.skipped_columns:
            print('# Skipped columns #')
            for column_meta in meta.skipped_columns:
                column_meta.pretty_print()
    return metas


def domain_has_excel_dashboard_access(domain):
    return domain_has_privilege(domain, EXCEL_DASHBOARD)


def domain_has_daily_saved_export_access(domain):
    return domain_has_privilege(domain, DAILY_SAVED_EXPORT)
