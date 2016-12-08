from soil import DownloadBase, CachedDownload, FileDownload, MultipleTaskDownload
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


def get_download_context(download_id, check_state=False, message=None, require_result=False):
    """
    :param require_result: If set to True, is_ready will not be set to True unless result is
    also available. If check_state=False, this is ignored.
    """
    is_ready = False
    context = {}
    download_data = DownloadBase.get(download_id)
    context['has_file'] = download_data is not None and download_data.has_file
    if download_data is None:
        download_data = DownloadBase(download_id=download_id)

    if isinstance(download_data, MultipleTaskDownload):
        if download_data.task.ready():
            context['result'], context['error'] = _get_download_context_multiple_tasks(download_data)
    else:
        try:
            if download_data.task.failed():
                raise TaskFailedError()
        except (TypeError, NotImplementedError):
            # no result backend / improperly configured
            pass
        else:
            if not check_state:
                is_ready = True
            elif download_data.task.successful():
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
            getattr(settings, 'CELERY_ALWAYS_EAGER', False) or
            progress.get('percent', 0) == 100 and
            not progress.get('error', False)
        )

    context['is_ready'] = is_ready or progress_complete()
    if check_state and require_result:
        context['is_ready'] = context['is_ready'] and context.get('result') is not None
    context['is_alive'] = alive
    context['progress'] = progress
    context['download_id'] = download_id
    context['allow_dropbox_sync'] = isinstance(download_data, FileDownload) and download_data.use_transfer
    context['custom_message'] = message
    return context


def _get_download_context_multiple_tasks(download_data):
    """for grouped celery tasks, append all results to the context
    """
    results = download_data.task.results
    messages = []
    errors = []
    for result in results:
        try:
            task_result = result.get()
        except Exception as e:  # Celery raises whatever exception was thrown
                                # in the task when accessing the result
            errors.append(e)
        else:
            messages.append(task_result.get("messages"))

    return messages, errors
