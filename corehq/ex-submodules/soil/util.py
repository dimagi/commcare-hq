from __future__ import absolute_import
import os
import tempfile

from wsgiref.util import FileWrapper

from django.conf import settings
from django.utils.translation import ugettext as _
from django.urls import reverse

from couchexport.models import Format

from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.web import get_url_base

from soil import DownloadBase, CachedDownload, FileDownload, MultipleTaskDownload, BlobDownload
from soil.exceptions import TaskFailedError
from soil.heartbeat import is_alive, heartbeat_enabled
from soil.progress import get_task_status

from corehq.util.view_utils import absolute_reverse
from corehq.blobs import get_blob_db
from corehq.util.files import safe_filename_header

from zipfile import ZipFile


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
    send_HTML_email(_('CommCare Export Complete'), email_address, email_body)


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


class ExposeBlobDownload:
    """
        Takes path to a file,
        move its content to a ZipFile unless asked not to
        stores it's contents in BlobDb
        clean the input file after storing content to blobdb unless asked not to
        returns a link to download the file
    """
    def __init__(self, zip_file=True, cleanup=True):
        self.zip_file = zip_file
        self.cleanup = cleanup

    @staticmethod
    def save_dump_to_blob(data_file_path, data_file_name, result_file_format):
        with open(data_file_path, 'rb') as file_:
            blob_db = get_blob_db()
            blob_db.put(
                file_,
                data_file_name,
                timeout=60 * 24)  # 24 hours
        file_format = Format.from_format(result_file_format)
        file_name_header = safe_filename_header(
            data_file_name, file_format.extension)
        blob_dl_object = expose_blob_download(
            data_file_name,
            mimetype=file_format.mimetype,
            content_disposition=file_name_header
        )
        return blob_dl_object.download_id

    @staticmethod
    def zip_dump(data_file_path, data_file_name):
        _, zip_temp_path = tempfile.mkstemp(".zip")
        with ZipFile(zip_temp_path, 'w') as zip_file_:
            zip_file_.write(data_file_path, data_file_name)

        return zip_temp_path

    @staticmethod
    def clean_temp_files(*temp_file_paths):
        for file_path in temp_file_paths:
            os.remove(file_path)

    def get_link(self, data_file_path, data_file_name, result_file_format):
        if self.zip_file:
            temp_zip_path = self.zip_dump(data_file_path, data_file_name)
            download_id = self.save_dump_to_blob(temp_zip_path, data_file_name, result_file_format)
            self.clean_temp_files(temp_zip_path)
        else:
            download_id = self.save_dump_to_blob(data_file_path, data_file_name, result_file_format)
        if self.cleanup:
            self.clean_temp_files(data_file_path)
        url = "%s%s?%s" % (get_url_base(),
                           reverse('retrieve_download', kwargs={'download_id': download_id}),
                           "get_file")  # downloads immediately, rather than rendering page
        return url
