import kombu.utils.json as kombu_json
from celery import Task
from celery import states as celery_states
from celery.signals import task_postrun

from corehq.apps.celery.models import TaskRecord


class DurableTask(Task):
    """
    Only supports tasks configured with json serialization (i.e. no support for pickle)
    """

    def __init__(self):
        super().__init__()
        if getattr(self, 'durable', False) and self.serializer != 'json':
            raise UnsupportedSerializationError(
                f"Cannot create a durable task with {self.serializer} serialization."
                "Durable tasks only support JSON serialization."
            )

    def apply_async(self, args=None, kwargs=None, **opts):
        if not getattr(self, 'durable', False):
            return super().apply_async(args=args, kwargs=kwargs, **opts)

        headers = opts.pop('headers', {}) or {}
        headers['durable'] = True

        task_id = opts.get('task_id', None)
        defaults = {
            'name': self.name,
            'args': kombu_json.dumps(args),
            'kwargs': kombu_json.dumps(kwargs),
            'sent': False,
            'error': '',
        }
        try:
            result = super().apply_async(args=args, kwargs=kwargs, headers=headers, **opts)
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


@task_postrun.connect
def update_task_record(*, state, **kwargs):
    task = kwargs.get('task')
    try:
        headers = task.request.headers or {}
    except AttributeError:
        # if there are no headers, it isn't a durable task
        return

    if headers.get('durable', False) and state in celery_states.READY_STATES:
        record = TaskRecord.objects.get(task_id=task.request.id)
        record.delete()


class UnsupportedSerializationError(Exception):
    """Raised when attempting to use serialization other than JSON"""
