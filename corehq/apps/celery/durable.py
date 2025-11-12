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

        task_id = opts.get('task_id', None)
        defaults = {
            'name': self.name,
            'args': kombu_json.dumps(args),
            'kwargs': kombu_json.dumps(kwargs),
            'sent': False,
            'error': '',
        }
        try:
            result = super().apply_async(args=args, kwargs=kwargs, **opts)
            task_id = result.task_id
            defaults['sent'] = True
            return result
        except Exception as e:
            defaults['error'] = f"{type(e).__name__}: {e}"
            raise
        finally:
            # only provide update args if this is a retry (ie task_id was provided)
            # it is possible for an apply_async called via a retry to "beat" the original apply_async
            # call since the TaskRecord isn't created until after the task is sent to the broker.
            # To handle this edge case, ignore updating the TaskRecord if this is the original apply_async
            # by passing in an empty dict for defaults
            update_defaults = defaults if opts.get('task_id', None) else {}
            TaskRecord.objects.update_or_create(
                task_id=task_id, create_defaults=defaults, defaults=update_defaults
            )

    def after_return(self, state, retval, task_id, *args):
        if self.durable:
            delete_task_record(task_id, state)


def delete_task_record(task_id, state):
    if state in [celery_states.SUCCESS, celery_states.FAILURE]:
        record = TaskRecord.objects.get(task_id=task_id)
        record.delete()
    else:
        notify_error(
            "DurableTaskError",
            f"Unexpected call to delete_task_record for task id {task_id} in state {state}",
        )


class UnsupportedSerializationError(Exception):
    """Raised when attempting to use serialization other than JSON"""
