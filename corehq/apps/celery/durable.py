import json

from celery import Task


class DurableTask(Task):
    def apply_async(self, args=None, kwargs=None, **opts):
        from corehq.apps.celery.models import TaskRecord
        from corehq.util.json import CommCareJSONEncoder

        if not getattr(self, 'durable', False):
            return super().apply_async(args=args, kwargs=kwargs, **opts)

        headers = opts.pop('headers', {}) or {}
        headers['durable'] = True

        record = TaskRecord(
            name=self.name,
            args=json.dumps(args, cls=CommCareJSONEncoder),
            kwargs=json.dumps(kwargs, cls=CommCareJSONEncoder),
            sent=False,
        )
        try:
            result = super().apply_async(args=args, kwargs=kwargs, headers=headers, **opts)
            record.task_id = result.task_id
            record.sent = True
            return result
        except Exception as e:
            record.error = str(e)
            raise
        finally:
            record.save()
