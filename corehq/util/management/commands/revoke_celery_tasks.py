from django.core.management.base import BaseCommand
from corehq.util.celery_utils import revoke_tasks


class Command(BaseCommand):
    """
    Revokes celery tasks matching the given task names. It's best to leave this command
    running for a bit in order to get them all, as it will keep polling for tasks
    to revoke, and there might be tasks in the message queue which haven't been
    received by the worker yet.

    You can stop this process at any time with Ctrl+C.

    Example:
    python manage.py revoke_celery_tasks couchexport.tasks.export_async
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'task_names',
            metavar='task_name',
            nargs='+',
        )

    def handle(self, task_names, **options):
        try:
            revoke_tasks(task_names)
        except KeyboardInterrupt:
            pass
