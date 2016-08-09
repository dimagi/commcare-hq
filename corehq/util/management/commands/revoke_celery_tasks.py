from django.core.management.base import BaseCommand, CommandError
from corehq.util.celery_utils import revoke_tasks


class Command(BaseCommand):
    """
    Revokes celery tasks from the given worker. Note that there's a limit to the number
    of tasks returned from a call to app.control.inspect.<task state>, so if you want
    to revoke all of them, it's best to leave this command running for a little bit as it
    will continue to poll for new tasks that need to be revoked. You can stop this process
    at any time with Ctrl+C.

    Example:
    python manage.py revoke_celery_tasks couchexport.tasks.export_async
    """
    args = '<task name 1> <task name 2> ...'
    help = ''

    def handle(self, *args, **options):
        if len(args) == 0:
            raise CommandError("usage: python manage.py revoke_celery_tasks "
                "<task name 1> <task name 2> ...")

        try:
            revoke_tasks(args)
        except KeyboardInterrupt:
            pass
