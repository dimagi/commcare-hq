from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.motech.repeaters.models import Repeater


class Command(BaseCommand):
    help = f"""
    Sets or gets Repeater.max_workers, which is the number of Celery workers
    allocated to sending a batch of repeat records. Set to "0" to use
    the default, which is {settings.DEFAULT_REPEATER_WORKERS}. Set to
    "1" to send repeat records chronologically, one at a time. The
    maximum value is {settings.MAX_REPEATER_WORKERS}.

    If max_workers is not provided, returns the current value for the repeater.
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('repeater_id')
        parser.add_argument('max_workers', type=int, nargs='?')

    def _get_repeater(self, domain, repeater_id):
        try:
            return Repeater.objects.get(domain=domain, id=repeater_id)
        except Repeater.DoesNotExist:
            self.stderr.write(
                f'Repeater {repeater_id} was not found in domain {domain}.'
            )
            return None

    def _get_max_workers(self, repeater):
        self.stdout.write(str(repeater.max_workers))

    def _set_max_workers(self, domain, repeater_id, max_workers):
        if not 0 <= max_workers <= settings.MAX_REPEATER_WORKERS:
            self.stderr.write(
                'max_workers must be between 0 and '
                f'{settings.MAX_REPEATER_WORKERS}.'
            )
            return

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

    def handle(self, domain, repeater_id, max_workers, *args, **options):
        repeater = self._get_repeater(domain, repeater_id)
        if not repeater:
            return

        if max_workers is None:
            self._get_max_workers(repeater)
        else:
            self._set_max_workers(domain, repeater_id, max_workers)
