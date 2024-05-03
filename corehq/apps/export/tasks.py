import logging
from datetime import datetime, timedelta

from django.conf import settings

from celery.schedules import crontab

from couchexport.models import Format
from soil import DownloadBase
from soil.progress import get_task_status
from soil.util import expose_blob_download, process_email_request

from corehq.apps.celery import periodic_task, task
from corehq.apps.data_dictionary.util import add_properties_to_data_dictionary
from corehq.apps.export.exceptions import RejectedStaleExport
from corehq.apps.export.utils import get_export, get_default_export_settings_if_available
from corehq.apps.users.models import CouchUser
from corehq.blobs import CODES, get_blob_db
from corehq.celery_monitoring.signals import get_task_time_to_start
from corehq.util.decorators import serial_task
from corehq.util.files import TransientTempfile, safe_filename_header
from corehq.util.metrics import metrics_counter, metrics_track_errors
from corehq.util.quickcache import quickcache

from .const import EXPORT_DOWNLOAD_QUEUE, SAVED_EXPORTS_QUEUE
from .dbaccessors import (
    get_case_inferred_schema,
    get_daily_saved_export_ids_for_auto_rebuild,
    get_properly_wrapped_export_instance,
)
from .export import get_export_file, rebuild_export
from .models.new import (
    EmailExportWhenDoneRequest,
    CaseExportInstance,
    CaseExportDataSchema
)
from .system_properties import MAIN_CASE_TABLE_PROPERTIES
from django.core.cache import cache

logger = logging.getLogger('export_migration')


@task(queue=EXPORT_DOWNLOAD_QUEUE)
def populate_export_download_task(domain, export_ids, exports_type, username,
                                  es_filters, download_id, owner_id,
                                  filename=None, expiry=10 * 60):
    """
    :param expiry:  Time period for the export to be available for download in minutes
    """

    email_requests = EmailExportWhenDoneRequest.objects.filter(
        domain=domain,
        download_id=download_id
    )

    if settings.STALE_EXPORT_THRESHOLD is not None and not email_requests.count():
        delay = get_task_time_to_start(populate_export_download_task.request.id)
        if delay.total_seconds() > settings.STALE_EXPORT_THRESHOLD:
            metrics_counter('commcare.exports.rejected_unfresh_export')
            raise RejectedStaleExport()

    export_instances = [get_export(exports_type, domain, export_id, username)
                        for export_id in export_ids]
    with TransientTempfile() as temp_path, metrics_track_errors('populate_export_download_task'):
        export_file = get_export_file(
            export_instances,
            es_filters,
            temp_path,
            # We don't have a great way to calculate progress if it's a bulk download,
            # so only track the progress for single instance exports.
            progress_tracker=populate_export_download_task if len(export_instances) == 1 else None
        )

        file_format = Format.from_format(export_file.format)
        filename = filename or export_instances[0].name

        with export_file as file_:
            db = get_blob_db()
            db.put(
                file_,
                domain=domain,
                parent_id=domain,
                type_code=CODES.data_export,
                key=download_id,
                timeout=expiry,
            )

            expose_blob_download(
                download_id,
                expiry=expiry * 60,
                mimetype=file_format.mimetype,
                content_disposition=safe_filename_header(filename, file_format.extension),
                download_id=download_id,
                owner_ids=[owner_id],
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


@task(queue=SAVED_EXPORTS_QUEUE, ignore_result=False, acks_late=True)
def _start_export_task(export_instance_id):
    export_instance = get_properly_wrapped_export_instance(export_instance_id)
    rebuild_export(export_instance, progress_tracker=_start_export_task)


def _get_saved_export_download_data(export_instance_id):
    prefix = DownloadBase.new_id_prefix
    download_id = '{}rebuild_export_tracker.{}'.format(prefix, export_instance_id)
    download_data = DownloadBase.get(download_id)
    if download_data is None:
        download_data = DownloadBase(download_id=download_id)
    return download_data


def rebuild_saved_export(export_instance_id, manual=False):
    """Kicks off a celery task to rebuild the export.

    If this is called while another one is already running for the same export
    instance, it will just noop.
    """
    download_data = _get_saved_export_download_data(export_instance_id)
    status = get_task_status(download_data.task)
    if manual and status.missing() and download_data.task:
        download_data.task.revoke(terminate=True)
    if status.not_started() or status.started():
        return

    # associate task with the export instance
    download_data.set_task(
        _start_export_task.apply_async(
            args=[export_instance_id],
            queue=EXPORT_DOWNLOAD_QUEUE if manual else SAVED_EXPORTS_QUEUE,
        )
    )


def get_saved_export_task_status(export_instance_id):
    """Get info on the ongoing rebuild task if one exists.

    (This is built with the assumption that there shouldn't be multiple
    rebuilds in progress for a single export instance)
    """
    download_data = _get_saved_export_download_data(export_instance_id)
    return get_task_status(download_data.task)


@serial_task('{domain}-{case_type}', queue='background_queue', serializer='pickle')
def add_inferred_export_properties(sender, domain, case_type, properties):
    _cached_add_inferred_export_properties(sender, domain, case_type, properties)


@periodic_task(run_every=crontab(hour="23", minute="59", day_of_week="*"),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def saved_exports():
    last_access_cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
    for daily_saved_export_id in get_daily_saved_export_ids_for_auto_rebuild(last_access_cutoff):
        rebuild_saved_export(daily_saved_export_id, manual=False)


@quickcache(['sender', 'domain', 'case_type', 'properties'], timeout=60 * 60)
def _cached_add_inferred_export_properties(sender, domain, case_type, properties):
    from corehq.apps.export.models import (
        MAIN_TABLE,
        CaseInferredSchema,
        PathNode,
        ScalarItem,
    )
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
def generate_schema_for_all_builds(self, export_type, domain, app_id, identifier):
    from .views.utils import GenerateSchemaFromAllBuildsView
    export_cls = GenerateSchemaFromAllBuildsView.export_cls(export_type)
    export_cls.generate_schema(
        domain,
        app_id,
        identifier,
        only_process_current_builds=False,
        task=self,
    )


@task(queue='background_queue')
def process_populate_export_tables(export_id, progress_id=None):
    """
    When creating a bulk case export instance, it will be created without any tables. This is because
    there may be a lot of case types on the project which can cause performance issues. The tables for
    the export instance are instead added async in this task after the instance has been saved.
    """
    export = CaseExportInstance.get(export_id)
    progress_data = {
        'table_name': export.name,
        'progress': 0
    }

    if progress_id:
        cache.set(progress_id, progress_data)

    schema = CaseExportDataSchema.generate_schema(export.domain, None, export.case_type)
    if progress_id:
        progress_data['progress'] = 50
        cache.set(progress_id, progress_data)

    export_settings = get_default_export_settings_if_available(export.domain)
    export_instance = CaseExportInstance.generate_instance_from_schema(
        schema,
        export_settings=export_settings,
        load_deprecated=False
    )
    export.tables = export_instance.tables
    export.save()

    if progress_id:
        cache.expire(progress_id, 0)
