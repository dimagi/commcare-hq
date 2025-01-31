from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.motech.repeaters.models import Repeater


class Command(BaseCommand):
    help = f"""
    Sets Repeater.max_workers, which is the number of Celery workers
    allocated to sending a batch of repeat records. Set to "0" to use
    the default, which is {settings.DEFAULT_REPEATER_WORKERS}. Set to
    "1" to send repeat records chronologically, one at a time. The
    maximum value is {settings.MAX_REPEATER_WORKERS}.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('repeater_id')
        parser.add_argument('max_workers', type=int)

    def handle(self, domain, repeater_id, max_workers, *args, **options):
        if not 0 <= max_workers <= settings.MAX_REPEATER_WORKERS:
            self.stderr.write(
                'max_workers must be between 0 and '
                f'{settings.MAX_REPEATER_WORKERS}.'
            )
        # Use QuerySet.update() to avoid a race condition if the
        # repeater is currently in use.
        rows = (
            Repeater.objects
            .filter(domain=domain, id=repeater_id)
            .update(max_workers=max_workers)
        )
        if not rows:
            self.stderr.write(
                f'Repeater {repeater_id} was not found in domain {domain}.'
            )
