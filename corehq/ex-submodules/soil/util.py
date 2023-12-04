import datetime
import os
import tempfile
from wsgiref.util import FileWrapper

from django.conf import settings
from django.utils.translation import gettext as _

from couchexport.models import Format
from dimagi.utils.django.email import send_HTML_email
from soil import (
    BlobDownload,
    CachedDownload,
    DownloadBase,
    FileDownload,
    MultipleTaskDownload,
)
from soil.exceptions import TaskFailedError
from soil.progress import get_task_status

from corehq.celery_monitoring.heartbeat import (
    Heartbeat,
    HeartbeatNeverRecorded,
)
from corehq.util.view_utils import absolute_reverse


def expose_cached_download(payload, expiry, file_extension, mimetype=None,
                           content_disposition=None, download_id=None,
                           extras=None, owner_ids=None):
    """
    Expose a cache download object.
    """
    ref = CachedDownload.create(payload, expiry, mimetype=mimetype,
                                content_disposition=content_disposition,
                                download_id=download_id, extras=extras,
                                suffix=file_extension, owner_ids=owner_ids)
    ref.save(expiry)
    return ref


def expose_file_download(path, expiry, **kwargs):
    """
    Expose a file download object that potentially uses the external drive
    """
    ref = FileDownload(path, **kwargs)
    ref.save(expiry)
    return ref


def expose_blob_download(
        identifier,
        expiry,
        mimetype='text/plain',
        content_disposition=None,
        download_id=None,
        owner_ids=None):
    """
    Expose a blob object for download
    """
    # TODO add file parameter and refactor blob_db.put(...) into this method
    ref = BlobDownload(
        identifier,
        mimetype=mimetype,
        content_disposition=content_disposition,
        download_id=download_id,
        owner_ids=owner_ids,
    )
    ref.save(expiry)
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
        # Celery replaces exceptions with a wrapped one that we can't directly import
        # so I think our best choice is to match off the name, even though that's hacky
        exception_name = (task.result.__class__.__name__
                          if isinstance(task.result, Exception) else None)
        raise TaskFailedError([task_status.error], exception_name=exception_name)
    if require_result:
        is_ready = task_status.success() and task_status.result is not None
    else:
        is_ready = task_status.success()

    return {
        'result': task_status.result,
        'error': task_status.error,
        'is_ready': is_ready,
        'is_alive': _is_alive(),
        'progress': task_status.progress._asdict(),
        'download_id': download_id,
        'allow_dropbox_sync': isinstance(download_data, FileDownload) and download_data.use_transfer,
        'has_file': download_data is not None and download_data.has_file,
        'custom_message': message,
    }


def _is_alive():
    queue = getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
    try:
        blockage = Heartbeat(queue).get_blockage_duration()
        if blockage > datetime.timedelta(minutes=5):
            return False
        return True
    except HeartbeatNeverRecorded:
        return False


def process_email_request(domain, download_id, email_address):
    dropbox_url = absolute_reverse('dropbox_upload', args=(download_id,))
    download_url = "{}?get_file".format(absolute_reverse('retrieve_download', args=(download_id,)))
    try:
        allow_dropbox_sync = get_download_context(download_id).get('allow_dropbox_sync', False)
    except TaskFailedError:
        allow_dropbox_sync = False
    dropbox_message = ''
    if allow_dropbox_sync:
        dropbox_message = _('<br/><br/>You can also upload your data to Dropbox with the link below:<br/>'
                            '{}').format(dropbox_url)
    email_body = _('Your CommCare export for {} is ready! Click on the link below to download your requested data:'
                   '<br/>{}{}').format(domain, download_url, dropbox_message)
    send_HTML_email(_('CommCare Export Complete'), email_address, email_body,
                    domain=domain, use_domain_gateway=True,)


def get_task(task_id):
    from celery import Task
    return Task().AsyncResult(task_id)


def get_download_file_path(use_transfer, filename):
    if use_transfer:
        fpath = os.path.join(settings.SHARED_DRIVE_CONF.transfer_dir, filename)
    else:
        fd, fpath = tempfile.mkstemp()
        os.close(fd)

    return fpath


def expose_download(use_transfer, file_path, filename, download_id, file_type, owner_ids=None):
    common_kwargs = {
        'mimetype': Format.from_format(file_type).mimetype,
        'content_disposition': 'attachment; filename="{fname}"'.format(fname=filename),
        'download_id': download_id,
        'expiry': (1 * 60 * 60),
        'owner_ids': owner_ids,
    }
    if use_transfer:
        expose_file_download(
            file_path,
            use_transfer=use_transfer,
            **common_kwargs
        )
    else:
        expose_cached_download(
            FileWrapper(open(file_path, 'rb')),
            file_extension=file_type,
            **common_kwargs
        )
