from __future__ import absolute_import, division, unicode_literals

import logging
from collections import namedtuple

from django.conf import settings
from django.db import IntegrityError

import six
from celery.result import GroupResult

from soil.exceptions import TaskFailedError

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
        if not task:
            info = None
        else:
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
            if total == 0:
                percent = 100
            else:
                percent = current * 100 // total if total and current is not None else 0

    return TaskProgress(
        current=current,
        total=total,
        percent=percent,
        error=error,
        error_message=error_message,
    )


def set_task_progress(task, current, total):
    update_task_state(task, 'PROGRESS', {'current': current, 'total': total})


def update_task_state(task, state, meta):
    try:
        if task:
            task.update_state(state=state, meta=meta)
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

    if not task:
        progress = get_task_progress(None)
        context_result = False
        context_error = []
    elif is_multiple_download_task:
        if task.ready():
            context_result, context_error = _get_download_context_multiple_tasks(task)
        progress = get_multiple_task_progress(task)
    else:
        if task.failed():
            failed = True

        result = task.result
        if task.successful():
            is_ready = True
            context_result = result and result.get('messages')
        elif result and isinstance(result, Exception):
            context_error = six.text_type(result)
            if '\t' in context_error:
                context_error = [err for err in context_error.split('\t') if err]
        elif result and result.get('errors'):
            failed = True
            context_error = result.get('errors')
        progress = get_task_progress(task)

    def progress_complete():
        return (
            getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False) or
            progress and progress.percent == 100 and
            not progress.error
        )

    is_ready = is_ready or progress_complete()

    if failed:
        state = STATES.failed
        if isinstance(task.result, Exception) and not context_error:
            context_error = "%s: %s" % (type(task.result).__name__, task.result)
    elif is_ready:
        state = STATES.success
    elif task and _is_task_pending(task):
        state = STATES.not_started
    elif progress.percent is None:
        state = STATES.missing
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
