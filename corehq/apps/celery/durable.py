import json

from celery import Task
from celery import states as celery_states
from celery.exceptions import OperationalError
from celery.signals import task_postrun


class DurableTask(Task):
    def apply_async(self, args=None, kwargs=None, **opts):
        from corehq.apps.celery.models import TaskRecord, TaskRecordState
        from corehq.util.json import CommCareJSONEncoder

        if not getattr(self, 'durable', False):
            return super().apply_async(args=args, kwargs=kwargs, **opts)

        headers = opts.pop('headers', {}) or {}
        headers['durable'] = True
        result = state = None
        try:
            result = super().apply_async(args=args, kwargs=kwargs, headers=headers, **opts)
            return result
        except OperationalError:
            state = TaskRecordState.PENDING
            raise
        finally:
            if result:
                if result.state == celery_states.PENDING:
                    # Celery does not have a state to distinguish between "task created" and "sent to the broker"
                    # if we've made it here with a valid result, it was successfully sent to the broker
                    state = TaskRecordState.SENT
                else:
                    state = TaskRecordState.from_celery(result.state)

            TaskRecord.objects.create(
                task_id=result.task_id if result else None,
                name=self.name,
                args=json.dumps(args, cls=CommCareJSONEncoder),
                kwargs=json.dumps(kwargs, cls=CommCareJSONEncoder),
                state=state,
            )


@task_postrun.connect
def update_task_record(**kwargs):
    from corehq.apps.celery.models import TaskRecord, TaskRecordState

    task = kwargs.get('task')
    try:
        headers = task.request.headers
    except (NameError, AttributeError):
        # if there are no headers, it isn't a durable task
        return

    if headers.get('durable', False):
        record = TaskRecord.objects.get(task_id=task.request.id)
        record.state = TaskRecordState.from_celery(kwargs.get('state'))
        record.save()
