from soil import DownloadBase, CachedDownload, FileDownload
from soil.exceptions import TaskFailedError
from soil.heartbeat import heartbeat_enabled, is_alive
from django.conf import settings


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


def get_download_context(download_id, check_state=False):
    is_ready = False
    context = {}
    download_data = DownloadBase.get(download_id)
    context['has_file'] = bool(download_data)
    if download_data is None:
        download_data = DownloadBase(download_id=download_id)

    try:
        if download_data.task.failed():
            raise TaskFailedError()
    except (TypeError, NotImplementedError):
        # no result backend / improperly configured
        pass
    else:
        if not check_state:
            is_ready = True
        elif download_data.task.state == 'SUCCESS':
            is_ready = True
            result = download_data.task.result
            context['result'] = result and result.get('messages')
            if result and result.get('errors'):
                raise TaskFailedError(result.get('errors'))

    alive = True
    if heartbeat_enabled():
        alive = is_alive()

    progress = download_data.get_progress()

    def progress_complete():
        return (
            getattr(settings, 'CELERY_ALWAYS_EAGER', False) and
            progress.get('percent', 0) == 100 and
            not progress.get('error', False)
        )

    context['is_ready'] = is_ready or progress_complete()
    context['is_alive'] = alive
    context['progress'] = progress
    context['download_id'] = download_id
    return context
