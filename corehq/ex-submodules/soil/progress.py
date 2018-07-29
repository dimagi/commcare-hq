from __future__ import absolute_import, division
from __future__ import unicode_literals
import logging
from collections import namedtuple
from django.conf import settings
from django.db import IntegrityError
from celery.result import GroupResult


TaskProgress = namedtuple('TaskProgress',
                          ['current', 'total', 'percent', 'error', 'error_message'])


class STATES(object):
    missing = -1
    not_started = 0
    started = 1
    success = 2
    failed = 3


class TaskStatus(namedtuple('TaskStatus', ['result', 'error', 'state', 'progress'])):
    def missing(self):
        return self.state == STATES.missing

    def not_started(self):
        return self.state == STATES.not_started

    def started(self):
        return self.state == STATES.started

    def success(self):
        return self.state == STATES.success

    def failed(self):
        return self.state == STATES.failed


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
            percent = current * 100 // total if total and current is not None else 0
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


def get_task_status(task, is_multiple_download_task=False):
    context_result = None
    context_error = None
    is_ready = False
    failed = False
    if is_multiple_download_task:
        if task.ready():
            context_result, context_error = _get_download_context_multiple_tasks(task)
        progress = get_multiple_task_progress(task)
    else:
        try:
            if task.failed():
                failed = True
        except (TypeError, NotImplementedError):
            # no result backend / improperly configured
            pass
        else:
            if task.successful():
                is_ready = True
                result = task.result
                context_result = result and result.get('messages')
                if result and result.get('errors'):
                    failed = True
                    context_error = result.get('errors')
        progress = get_task_progress(task)

    def progress_complete():
        return (
            getattr(settings, 'CELERY_ALWAYS_EAGER', False) or
            progress.percent == 100 and
            not progress.error
        )

    is_ready = is_ready or progress_complete()

    if failed:
        state = STATES.failed
        if isinstance(task.result, Exception) and not context_error:
            context_error = "%s: %s" % (type(task.result).__name__, task.result)
    elif is_ready:
        state = STATES.success
    elif _is_task_pending(task):
        state = STATES.missing
    elif progress.percent is None:
        state = STATES.not_started
    else:
        state = STATES.started

    return TaskStatus(
        state=state,
        result=context_result,
        error=context_error,
        progress=progress,
    )


def _is_task_pending(task):
    if isinstance(task, GroupResult):
        return any([async_task.state == 'PENDING' for async_task in task.children])
    else:
        return task.state == 'PENDING'


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
            try:
                messages.append(task_result.get("messages"))
            except AttributeError:
                messages.append(str(task_result))

    return messages, errors
