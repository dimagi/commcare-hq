import logging
from collections import namedtuple
from django.conf import settings
from django.db import IntegrityError
from soil.exceptions import TaskFailedError
from soil.heartbeat import heartbeat_enabled, is_alive

TaskProgress = namedtuple('TaskProgress',
                          ['current', 'total', 'percent', 'error', 'error_message'])


TaskStatus = namedtuple('TaskStatus',
                        ['result', 'error', 'is_ready', 'is_alive', 'progress'])


def get_task_progress(task):
    error = False
    error_message = ''
    try:
        info = task.info
    except (TypeError, NotImplementedError):
        current = total = percent = None
        logging.exception("No celery result backend?")
    else:
        if info is None:
            current = total = percent = None
        elif isinstance(info, Exception):
            current = total = percent = 100
            error = True
            error_message = "%s: %s" % (type(info).__name__, info)
        else:
            current = info.get('current')
            total = info.get('total')
            percent = int(
                current * 100. / total if total and current is not None
                else 0
            )
    return TaskProgress(
        current=current,
        total=total,
        percent=percent,
        error=error,
        error_message=error_message,
    )


def set_task_progress(task, current, total):
    try:
        if task:
            task.update_state(state='PROGRESS', meta={'current': current, 'total': total})
    except (TypeError, NotImplementedError):
        pass
    except IntegrityError:
        # Not called in task context just pass
        pass


def get_multiple_task_progress(task):
    current = sum(int(result.ready()) for result in task.results)
    total = len(task.subtasks)
    percent = current * 100 // total if total and current is not None else 0
    return TaskProgress(
        current=current,
        total=total,
        percent=percent,
        error=None,
        error_message=None,
    )


def get_task_status(task, require_result=False, is_multiple_download_task=False):
    context_result = None
    context_error = None
    is_ready = False
    if is_multiple_download_task:
        if task.ready():
            context_result, context_error = _get_download_context_multiple_tasks(task)
        progress = get_multiple_task_progress(task)
    else:
        try:
            if task.failed():
                raise TaskFailedError()
        except (TypeError, NotImplementedError):
            # no result backend / improperly configured
            pass
        else:
            if task.successful():
                is_ready = True
                result = task.result
                context_result = result and result.get('messages')
                if result and result.get('errors'):
                    raise TaskFailedError(result.get('errors'))
        progress = get_task_progress(task)

    alive = True
    if heartbeat_enabled():
        alive = is_alive()

    def progress_complete():
        return (
            getattr(settings, 'CELERY_ALWAYS_EAGER', False) or
            progress.percent == 100 and
            not progress.error
        )

    is_ready = is_ready or progress_complete()
    if require_result:
        is_ready = is_ready and context_result is not None
    return TaskStatus(
        result=context_result,
        error=context_error,
        is_ready=is_ready,
        is_alive=alive,
        progress=progress,
    )


def _get_download_context_multiple_tasks(task):
    """for grouped celery tasks, append all results to the context
    """
    results = task.results
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
