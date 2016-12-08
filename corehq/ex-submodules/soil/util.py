from soil import DownloadBase, CachedDownload, FileDownload, MultipleTaskDownload
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
        task, require_result=require_result,
        is_multiple_download_task=isinstance(download_data, MultipleTaskDownload)
    )

    return {
        'result': task_status.result,
        'error': task_status.error,
        'is_ready': task_status.is_ready,
        'is_alive': task_status.is_alive,
        'progress': task_status.progress,
        'download_id': download_id,
        'allow_dropbox_sync': isinstance(download_data, FileDownload) and download_data.use_transfer,
        'has_file': download_data is not None and download_data.has_file,
        'custom_message': message,
    }
