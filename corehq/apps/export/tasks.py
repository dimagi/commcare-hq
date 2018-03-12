from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from celery.task import task

from corehq.apps.data_dictionary.util import add_properties_to_data_dictionary
from corehq.apps.export.export import get_export_file, rebuild_export, should_rebuild_export
from corehq.apps.export.dbaccessors import get_case_inferred_schema, get_properly_wrapped_export_instance
from corehq.apps.export.system_properties import MAIN_CASE_TABLE_PROPERTIES
from corehq.apps.export.models.new import EmailExportWhenDoneRequest
from corehq.apps.users.models import CouchUser
from corehq.util.decorators import serial_task
from corehq.util.files import safe_filename_header
from corehq.util.quickcache import quickcache
from corehq.blobs import get_blob_db
from couchexport.models import Format
from dimagi.utils.couch import CriticalSection
from soil.util import expose_blob_download, process_email_request
from six.moves import filter


logger = logging.getLogger('export_migration')


@task
def populate_export_download_task(export_instances, filters, download_id, filename=None, expiry=10 * 60 * 60):
    export_file = get_export_file(
        export_instances,
        filters,
        # We don't have a great way to calculate progress if it's a bulk download,
        # so only track the progress for single instance exports.
        progress_tracker=populate_export_download_task if len(export_instances) == 1 else None
    )

    file_format = Format.from_format(export_file.format)
    filename = filename or export_instances[0].name

    with export_file as file_:
        db = get_blob_db()
        db.put(file_, download_id, timeout=expiry)

        expose_blob_download(
            download_id,
            mimetype=file_format.mimetype,
            content_disposition=safe_filename_header(filename, file_format.extension),
            download_id=download_id,
        )

    domain = export_instances[0].domain
    email_requests = EmailExportWhenDoneRequest.objects.filter(
        domain=domain,
        download_id=download_id
    )
    for email_request in email_requests:
        try:
            couch_user = CouchUser.get_by_user_id(email_request.user_id, domain=domain)
        except CouchUser.AccountTypeError:
            pass
        else:
            if couch_user is not None:
                process_email_request(domain, download_id, couch_user.get_email())
    email_requests.delete()


@task(queue='background_queue', ignore_result=True)
def rebuild_export_task(export_instance_id, last_access_cutoff=None, filter=None):
    keys = ['rebuild_export_task_%s' % export_instance_id]
    timeout = 48 * 3600  # long enough to make sure this doesn't get called while another one is running
    with CriticalSection(keys, timeout=timeout, block=False) as locked_section:
        if locked_section.success():
            export_instance = get_properly_wrapped_export_instance(export_instance_id)
            if should_rebuild_export(export_instance, last_access_cutoff):
                rebuild_export(export_instance, filter)


@serial_task('{domain}-{case_type}', queue='background_queue')
def add_inferred_export_properties(sender, domain, case_type, properties):
    _cached_add_inferred_export_properties(sender, domain, case_type, properties)


@quickcache(['sender', 'domain', 'case_type', 'properties'], timeout=60 * 60)
def _cached_add_inferred_export_properties(sender, domain, case_type, properties):
    from corehq.apps.export.models import MAIN_TABLE, PathNode, CaseInferredSchema, ScalarItem
    """
    Adds inferred properties to the inferred schema for a case type.

    :param: sender - The signal sender
    :param: domain
    :param: case_type
    :param: properties - An iterable of case properties to add to the inferred schema
    """

    assert domain, 'Must have domain'
    assert case_type, 'Must have case type'
    assert all(['.' not in prop for prop in properties]), 'Properties should not have periods'
    inferred_schema = get_case_inferred_schema(domain, case_type)
    if not inferred_schema:
        inferred_schema = CaseInferredSchema(
            domain=domain,
            case_type=case_type,
        )
    group_schema = inferred_schema.put_group_schema(MAIN_TABLE)
    add_properties_to_data_dictionary(domain, case_type, properties)

    for case_property in properties:
        path = [PathNode(name=case_property)]
        system_property_column = list(filter(
            lambda column: column.item.path == path and column.item.transform is None,
            MAIN_CASE_TABLE_PROPERTIES,
        ))

        if system_property_column:
            assert len(system_property_column) == 1
            column = system_property_column[0]
            group_schema.put_item(path, inferred_from=sender, item_cls=column.item.__class__)
        else:
            group_schema.put_item(path, inferred_from=sender, item_cls=ScalarItem)

    inferred_schema.save()


@task(queue='background_queue', bind=True)
def generate_schema_for_all_builds(self, schema_cls, domain, app_id, identifier):
    schema_cls.generate_schema_from_builds(
        domain,
        app_id,
        identifier,
        only_process_current_builds=False,
        task=self,
    )
