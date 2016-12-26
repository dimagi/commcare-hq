import urllib
import logging
from celery.task import task

from corehq.apps.export.dbaccessors import get_inferred_schema
from corehq.apps.export.const import SCHEMA_GENERATION_TIMEOUT
from corehq.util.decorators import serial_task
from corehq.util.quickcache import quickcache
from couchexport.models import Format
from couchexport.tasks import escape_quotes
from soil.util import expose_cached_download

logger = logging.getLogger('export_migration')


@task
def populate_export_download_task(export_instances, filters, download_id, filename=None, expiry=10 * 60 * 60):
    from corehq.apps.export.export import get_export_file

    export_file = get_export_file(
        export_instances,
        filters,
        # We don't have a great way to calculate progress if it's a bulk download,
        # so only track the progress for single instance exports.
        progress_tracker=populate_export_download_task if len(export_instances) == 1 else None
    )

    file_format = Format.from_format(export_file.format)
    filename = filename or export_instances[0].name
    escaped_filename = escape_quotes('%s.%s' % (filename, file_format.extension))
    escaped_filename = urllib.quote(escaped_filename.encode('utf8'))

    payload = export_file.file.payload
    expose_cached_download(
        payload,
        expiry,
        ".{}".format(file_format.extension),
        mimetype=file_format.mimetype,
        content_disposition='attachment; filename="%s"' % escaped_filename,
        download_id=download_id,
    )
    export_file.file.delete()


@task(queue='background_queue', ignore_result=True)
def rebuild_export_task(export_instance, last_access_cutoff=None, filter=None):
    from corehq.apps.export.export import rebuild_export

    rebuild_export(export_instance, last_access_cutoff, filter)


@serial_task('{domain}-{case_type}', queue='background_queue')
def add_inferred_export_properties(sender, domain, case_type, properties):
    _cached_add_inferred_export_properties(sender, domain, case_type, properties)


@quickcache(['sender', 'domain', 'case_type', 'properties'], timeout=60 * 60)
def _cached_add_inferred_export_properties(sender, domain, case_type, properties):
    from corehq.apps.export.models import MAIN_TABLE, PathNode, InferredSchema, ScalarItem
    from corehq.apps.export.system_properties import MAIN_CASE_TABLE_PROPERTIES
    from corehq.apps.data_dictionary.util import add_properties_to_data_dictionary
    """
    Adds inferred properties to the inferred schema for a case type.

    :param: sender - The signal sender
    :param: domain
    :param: case_type
    :param: properties - An iterable of case properties to add to the inferred schema
    """

    assert domain, 'Must have domain'
    assert case_type, 'Must have case type'
    assert all(map(lambda prop: '.' not in prop, properties)), 'Properties should not have periods'
    inferred_schema = get_inferred_schema(domain, case_type)
    if not inferred_schema:
        inferred_schema = InferredSchema(
            domain=domain,
            case_type=case_type,
        )
    group_schema = inferred_schema.put_group_schema(MAIN_TABLE)
    add_properties_to_data_dictionary(domain, case_type, properties)

    for case_property in properties:
        path = [PathNode(name=case_property)]
        system_property_column = filter(
            lambda column: column.item.path == path,
            MAIN_CASE_TABLE_PROPERTIES,
        )

        if system_property_column:
            assert len(system_property_column) == 1
            column = system_property_column[0]
            group_schema.put_item(path, inferred_from=sender, item_cls=column.item.__class__)
        else:
            group_schema.put_item(path, inferred_from=sender, item_cls=ScalarItem)

    inferred_schema.save()


@task(soft_time_limit=SCHEMA_GENERATION_TIMEOUT)
def update_schema_with_builds_task(schema_cls, schema, identifier, app_build_ids):
    return schema_cls.update_schema_with_builds(schema, identifier, app_build_ids)


@task
def generate_delayed_schema(schema_cls, domain, app_id, identifier, app_build_ids):
    current_schema = schema_cls.get_latest_export_schema(domain, app_id, identifier)

    # If there's not an original schema, that means that it got deleted somehow or
    # error'd in saving. This is a rare event; we should ignore merging the delayed
    # schema if it occurs.
    if not current_schema:
        return

    delayed_schema = schema_cls.update_schema_with_builds(current_schema, identifier, app_build_ids)
    current_schema = schema_cls._merge_schemas(current_schema, delayed_schema)
    current_schema.processing_delayed_schemas = False
    current_schema = schema_cls._save_export_schema(
        current_schema,
        current_schema._id,
        current_schema._rev
    )
    return current_schema
