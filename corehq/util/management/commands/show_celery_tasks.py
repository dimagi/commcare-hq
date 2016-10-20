from django.core.management.base import BaseCommand, CommandError
from corehq.util.celery_utils import print_tasks, InvalidTaskTypeError


class Command(BaseCommand):
    """
    Prints celery tasks that have been received by the given worker that are in the
    given state.

    Task state can be: active, reserved, scheduled, or revoked.

    Example:
    python manage.py show_celery_tasks celery@hqcelery0.internal-va.commcarehq.org_main active
    """
    args = '<worker name> <task state>'
    help = ''

    def handle(self, *args, **options):
        if len(args) != 2:
            raise CommandError("usage: python manage.py show_celery_tasks <worker name> <task state>")

        try:
            print_tasks(args[0], args[1])
        except InvalidTaskTypeError as e:
            raise CommandError(str(e))
