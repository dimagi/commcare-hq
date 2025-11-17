import kombu.utils.json as kombu_json
from celery import Task
from celery import states as celery_states
from dimagi.utils.logging import notify_error

from corehq.apps.celery.models import TaskRecord


class DurableTask(Task):
    """
    Only supports tasks configured with json serialization (i.e. no support for pickle)
    """

    def __init__(self):
        super().__init__()
        self.durable = getattr(self, 'durable', False)
        if self.durable and self.serializer != 'json':
            raise UnsupportedSerializationError(
                f"Cannot create a durable task with {self.serializer} serialization."
                "Durable tasks only support JSON serialization."
            )

    def apply_async(self, args=None, kwargs=None, **opts):
        if not self.durable:
            return super().apply_async(args=args, kwargs=kwargs, **opts)

        defaults = {
            'name': self.name,
            'args': kombu_json.dumps(args),
            'kwargs': kombu_json.dumps(kwargs),
        }
        existing_task_id = opts.pop('task_id', None)
        is_retry = existing_task_id is not None
        # upsert instead of get and insert/update
        # more efficient than TaskRecord.objects.update_or_create(task_id=task_id, **defaults)
        (record,) = TaskRecord.objects.bulk_create(
            [TaskRecord(task_id=existing_task_id, **defaults)],
            ignore_conflicts=not is_retry,
            update_conflicts=is_retry,
            # unique_fields and update_fields are only used when update_conflicts=True
            unique_fields=['task_id'] if is_retry else None,
            update_fields=list(defaults) if is_retry else None,
        )
        try:
            return super().apply_async(args=args, kwargs=kwargs, task_id=record.task_id, **opts)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            TaskRecord.objects.filter(task_id=record.task_id).update(error=error)
            raise

    def after_return(self, state, retval, task_id, *args):
        if self.durable:
            delete_task_record(task_id, state)


def delete_task_record(task_id, state):
    if state in [celery_states.SUCCESS, celery_states.FAILURE]:
        TaskRecord.objects.filter(task_id=task_id).delete()
    else:
        notify_error(
            "DurableTaskError",
            f"Unexpected call to delete_task_record for task id {task_id} in state {state}",
        )


class UnsupportedSerializationError(Exception):
    """Raised when attempting to use serialization other than JSON"""
