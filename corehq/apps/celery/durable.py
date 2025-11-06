import kombu.utils.json as kombu_json
from celery import Task
from celery import states as celery_states
from celery.signals import task_postrun
from dimagi.utils.logging import notify_exception

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

        record = None
        task_id = opts.get('task_id', None)
        if task_id:
            # if a task calls `self.retry()`, it triggers another apply_async call
            try:
                record = TaskRecord.objects.get(task_id=task_id)
            except TaskRecord.DoesNotExist as e:
                notify_exception(
                    None,
                    f'Unexpectedly could not find TaskRecord object for id {task_id}',
                    details={'error': str(e)},
                )

        if record is None:
            record = TaskRecord(
                name=self.name,
                args=kombu_json.dumps(args),
                kwargs=kombu_json.dumps(kwargs),
                sent=False,
            )

        try:
            result = super().apply_async(args=args, kwargs=kwargs, headers=headers, **opts)
            record.task_id = result.task_id
            record.sent = True
            return result
        except Exception as e:
            record.error = f"{type(e).__name__}: {e}"
            raise
        finally:
            record.save()


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
