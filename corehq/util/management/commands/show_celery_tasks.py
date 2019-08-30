from django.core.management.base import BaseCommand, CommandError
from corehq.util.celery_utils import print_tasks, InvalidTaskTypeError


class Command(BaseCommand):
    """
    Prints celery tasks that have been received by the given worker that are in the
    given state.

    Example:
    python manage.py show_celery_tasks celery@hqcelery0.internal-va.commcarehq.org_main active
    """

    def add_arguments(self, parser):
        parser.add_argument('worker_name')
        parser.add_argument('task_state', choices=('active', 'reserved', 'scheduled', 'revoked'))

    def handle(self, worker_name, task_state, **options):
        try:
            print_tasks(worker_name, task_state)
        except InvalidTaskTypeError as e:
            raise CommandError(str(e))
