from __future__ import absolute_import
import os
import tempfile

from wsgiref.util import FileWrapper

from django.conf import settings

from couchexport.models import Format

from soil import DownloadBase, CachedDownload, FileDownload, MultipleTaskDownload, BlobDownload
from soil.exceptions import TaskFailedError
from soil.heartbeat import is_alive, heartbeat_enabled
from soil.progress import get_task_status


def expose_cached_download(payload, expiry, file_extension, mimetype=None,
                           content_disposition=None, download_id=None,
                           extras=None):
    """
    Expose a cache download object.
    """
    ref = CachedDownload.create(payload, expiry, mimetype=mimetype,
                                content_disposition=content_disposition,
                                download_id=download_id, extras=extras,
                                suffix=file_extension)
    ref.save(expiry)
    return ref


def expose_file_download(path, **kwargs):
    """
    Expose a file download object that potentially uses the external drive
    """
    ref = FileDownload.create(path, **kwargs)
    ref.save()
    return ref


def expose_blob_download(
        identifier,
        mimetype='text/plain',
        content_disposition=None,
        download_id=None):
    """
    Expose a blob object for download
    """
    ref = BlobDownload.create(
        identifier,
        mimetype=mimetype,
        content_disposition=content_disposition,
        download_id=download_id,
    )
    ref.save()
    return ref


def get_download_context(download_id, message=None, require_result=False):
    """
    :param require_result: If set to True, is_ready will not be set to True unless result is
    also available. If check_state=False, this is ignored.
    """
    download_data = DownloadBase.get(download_id)
    if download_data is None:
        download_data = DownloadBase(download_id=download_id)

    task = download_data.task

    task_status = get_task_status(
        task, is_multiple_download_task=isinstance(download_data, MultipleTaskDownload))
    if task_status.failed():
        raise TaskFailedError(task_status.error)
    if require_result:
        is_ready = task_status.success() and task_status.result is not None
    else:
        is_ready = task_status.success()

    return {
        'result': task_status.result,
        'error': task_status.error,
        'is_ready': is_ready,
        'is_alive': is_alive() if heartbeat_enabled() else True,
        'progress': task_status.progress._asdict(),
        'download_id': download_id,
        'allow_dropbox_sync': isinstance(download_data, FileDownload) and download_data.use_transfer,
        'has_file': download_data is not None and download_data.has_file,
        'custom_message': message,
    }


def get_task(task_id):
    from celery.task.base import Task
    return Task.AsyncResult(task_id)


def get_download_file_path(use_transfer, filename):
    if use_transfer:
        fpath = os.path.join(settings.SHARED_DRIVE_CONF.transfer_dir, filename)
    else:
        _, fpath = tempfile.mkstemp()

    return fpath


def expose_download(use_transfer, file_path, filename, download_id, file_type):
    common_kwargs = dict(
        mimetype=Format.from_format(file_type).mimetype,
        content_disposition='attachment; filename="{fname}"'.format(fname=filename),
        download_id=download_id,
    )
    if use_transfer:
        expose_file_download(
            file_path,
            use_transfer=use_transfer,
            **common_kwargs
        )
    else:
        expose_cached_download(
            FileWrapper(open(file_path, 'r')),
            expiry=(1 * 60 * 60),
            file_extension=file_type,
            **common_kwargs
        )
