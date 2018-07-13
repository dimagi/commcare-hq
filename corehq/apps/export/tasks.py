from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta
import logging
from functools import wraps

import six
from celery.schedules import crontab
from celery.task import task, periodic_task
from django.conf import settings
from soil import DownloadBase
from soil.progress import get_task_status

from corehq.apps.data_dictionary.util import add_properties_to_data_dictionary
from corehq.apps.reports.models import HQGroupExportConfiguration
from corehq.apps.users.models import CouchUser
from corehq.blobs import get_blob_db
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class
from corehq.util.datadog.gauges import datadog_track_errors
from corehq.util.decorators import serial_task
from corehq.util.files import safe_filename_header, TransientTempfile
from corehq.util.quickcache import quickcache
from couchexport.groupexports import export_for_group
from couchexport.models import Format
from soil.util import expose_blob_download, process_email_request

from .const import SAVED_EXPORTS_QUEUE, EXPORT_DOWNLOAD_QUEUE
from .dbaccessors import (
    get_case_inferred_schema,
    get_properly_wrapped_export_instance,
    get_all_daily_saved_export_instance_ids,
)
from .export import get_export_file, rebuild_export, should_rebuild_export
from .models.new import EmailExportWhenDoneRequest
from .system_properties import MAIN_CASE_TABLE_PROPERTIES

from six.moves import filter


def logged_export_task(func):

    def get_export_instance_ids(args, kwargs):
        if args:
            return [args[0]] if isinstance(args[0], six.string_types) else args[0]
        if 'export_instance_id' in kwargs:
            return [kwargs['export_instance_id']]
        if 'export_instance_ids' in kwargs:
            return kwargs['export_instance_ids']
        return []

    def get_inst_str(export_instance_id):
        export_instance = get_properly_wrapped_export_instance(export_instance_id)
        return '; '.join((
            'ID: {}'.format(export_instance._id),
            'Name: {}'.format(export_instance.name),
            'Domain: {}'.format(export_instance.domain),
        ))

    def get_task_str(export_func, args, kwargs):
        export_instance_ids = get_export_instance_ids(args, kwargs)
        inst_str = '), ('.join((get_inst_str(doc_id) for doc_id in export_instance_ids))
        task_str = 'Task: {}; Export instances: [({})]'.format(export_func.__name__, inst_str)
        return task_str

    @wraps(func)
    def log_export_task(*args, **kwargs):
        logger = logging.getLogger('export_tasks')

        task_str = get_task_str(func, args, kwargs)
        logger.info('Started {}'.format(task_str))
        started_at = datetime.utcnow()
        result = func(*args, **kwargs)
        duration = datetime.utcnow() - started_at
        logger.info('Completed {}; Duration {}'.format(task_str, duration))
        return result

    return log_export_task


@task(queue=EXPORT_DOWNLOAD_QUEUE)
@logged_export_task
def populate_export_download_task(export_instance_ids, filters, download_id, filename=None, expiry=10 * 60 * 60):
    export_instances = [get_properly_wrapped_export_instance(doc_id) for doc_id in export_instance_ids]
    with TransientTempfile() as temp_path, datadog_track_errors('populate_export_download_task'):
        export_file = get_export_file(
            export_instances,
            filters,
            temp_path,
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


@task(queue=SAVED_EXPORTS_QUEUE, ignore_result=True)
@logged_export_task
def _start_export_task(export_instance_id, last_access_cutoff):
    export_instance = get_properly_wrapped_export_instance(export_instance_id)
    if should_rebuild_export(export_instance, last_access_cutoff):
        rebuild_export(export_instance, progress_tracker=_start_export_task)


def _get_saved_export_download_data(export_instance_id):
    download_id = 'rebuild_export_tracker.{}'.format(export_instance_id)
    download_data = DownloadBase.get(download_id)
    if download_data is None:
        download_data = DownloadBase(download_id=download_id)
    return download_data


def rebuild_saved_export(export_instance_id, last_access_cutoff=None, manual=False):
    """Kicks off a celery task to rebuild the export.

    If this is called while another one is already running for the same export
    instance, it will just noop.
    """
    download_data = _get_saved_export_download_data(export_instance_id)
    status = get_task_status(download_data.task)
    if manual:
        if status.not_started() or status.missing():
            # cancel pending task before kicking off a new one
            # (May result in many revoked tasks if users kick off the
            # same export several times.)
            download_data.task.revoke()
        if status.started():
            return  # noop - make the user wait before starting a new one
    else:
        if status.not_started() or status.started():
            return  # noop - one's already on the way

    queue = EXPORT_DOWNLOAD_QUEUE if manual else SAVED_EXPORTS_QUEUE
    # associate task with the export instance
    download_data.set_task(
        _start_export_task.apply_async(
            args=[
                export_instance_id, last_access_cutoff
            ],
            queue=queue,
        )
    )


def get_saved_export_task_status(export_instance_id):
    """Get info on the ongoing rebuild task if one exists.

    (This is built with the assumption that there shouldn't be multiple
    rebuilds in progress for a single export instance)
    """
    download_data = _get_saved_export_download_data(export_instance_id)
    return get_task_status(download_data.task)


@serial_task('{domain}-{case_type}', queue='background_queue')
def add_inferred_export_properties(sender, domain, case_type, properties):
    _cached_add_inferred_export_properties(sender, domain, case_type, properties)


@task(queue=SAVED_EXPORTS_QUEUE, ignore_result=True)
def export_for_group_async(group_config_id):
    # exclude exports not accessed within the last 7 days
    last_access_cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
    group_config = HQGroupExportConfiguration.get(group_config_id)
    export_for_group(group_config, last_access_cutoff=last_access_cutoff)


@periodic_task(run_every=crontab(hour="23", minute="59", day_of_week="*"),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def saved_exports():
    for group_config_id in get_doc_ids_by_class(HQGroupExportConfiguration):
        export_for_group_async.delay(group_config_id)

    for daily_saved_export_id in get_all_daily_saved_export_instance_ids():
        last_access_cutoff = datetime.utcnow() - timedelta(days=settings.SAVED_EXPORT_ACCESS_CUTOFF)
        rebuild_saved_export(daily_saved_export_id, last_access_cutoff, manual=False)


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
