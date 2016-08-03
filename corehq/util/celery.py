from celery import Celery
from django.conf import settings


def revoke_tasks(worker, task_name):
    """
    Example:
    revoke_tasks(
        'celery@hqcelery0.internal-va.commcarehq.org_main',
        'couchexport.tasks.export_async'
    )
    """
    app = Celery()
    app.config_from_object(settings)
    task_ids = set()
    while True:
        for i in range(10):
            inspect = app.control.inspect([worker])
            reserved = inspect.reserved()
            if reserved is not None:
                break
        if reserved is None:
            break
        for task in reserved[worker]:
            task_id = task['id']
            if task['name'] == task_name and task_id not in task_ids:
                app.control.revoke(task_id)
                task_ids.add(task_id)
                print task_id
        print 'revoked %s tasks' % len(task_ids)
