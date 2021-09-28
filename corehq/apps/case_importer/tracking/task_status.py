from dimagi.ext import jsonobject
from dimagi.utils.logging import notify_exception
from soil.progress import STATES, get_task_status
from soil.util import get_task


class TaskStatus(jsonobject.StrictJsonObject):
    # takes on values of soil.progress.STATES
    state = jsonobject.IntegerProperty()
    progress = jsonobject.ObjectProperty(lambda: TaskStatusProgress)
    result = jsonobject.ObjectProperty(lambda: TaskStatusResult)

    def is_finished(self):
        return self.state in (STATES.success, STATES.failed)


class TaskStatusProgress(jsonobject.StrictJsonObject):
    percent = jsonobject.IntegerProperty()


class TaskStatusResult(jsonobject.StrictJsonObject):
    match_count = jsonobject.IntegerProperty()
    created_count = jsonobject.IntegerProperty()
    num_chunks = jsonobject.IntegerProperty()
    errors = jsonobject.ListProperty(lambda: TaskStatusResultError)


class TaskStatusResultError(jsonobject.StrictJsonObject):
    title = jsonobject.StringProperty()
    description = jsonobject.StringProperty()
    column = jsonobject.StringProperty()
    # usually an int, but field has been hijacked to include other debug info
    # search 'row_number=' in tasks.py
    # longer-term solution would be to have another field for debug info
    rows = jsonobject.ListProperty()


def normalize_task_status_result(result):
    if result:
        return TaskStatusResult(
            match_count=result['match_count'],
            created_count=result['created_count'],
            num_chunks=result['num_chunks'],
            errors=normalize_task_status_result_errors(result),
        )
    else:
        return None


def normalize_task_status_result_errors(result):
    """
    result is the return value of do_import

    it is important that when changes are made to the return value of do_import
    this function remains backwards compatible,
    i.e. compatible with old return values of do_import,
    because those values are saved directly in the database,
    and we need to be able to process them in the future
    """
    result_errors = []
    for _, columns_to_error_value in result['errors'].items():
        for column_name, error_value in columns_to_error_value.items():
            result_errors.append(TaskStatusResultError(
                title=str(error_value['error']),
                description=str(error_value['description']),
                column=column_name,
                rows=error_value['rows']
            ))
    return result_errors


def get_task_status_json(task_id):
    try:
        task_status = get_task_status(get_task(task_id))
    except Exception:
        # There was a period of time where the format of metadata we were setting
        # from the task would cause a celery-internal failure
        notify_exception(None, "Error fetching task")
        return TaskStatus(
            state=STATES.failed,
            progress=None,
            result=TaskStatusResult(errors=[TaskStatusResultError(description='Unknown Failure')]),
        )

    if task_status.state == STATES.failed:
        errors = (
            task_status.error if isinstance(task_status.error, (list, tuple))
            else [task_status.error]
        )
        return TaskStatus(
            state=task_status.state,
            progress=TaskStatusProgress(
                percent=task_status.progress.percent,
            ),
            result=TaskStatusResult(errors=[TaskStatusResultError(description=error)
                                            for error in errors]),
        )
    else:
        return TaskStatus(
            state=task_status.state,
            progress=TaskStatusProgress(
                percent=task_status.progress.percent,
            ),
            result=normalize_task_status_result(task_status.result),
        )


def make_task_status_success(result):
    return TaskStatus(
        state=STATES.success,
        progress=TaskStatusProgress(
            percent=0,
        ),
        result=normalize_task_status_result(result),
    )
