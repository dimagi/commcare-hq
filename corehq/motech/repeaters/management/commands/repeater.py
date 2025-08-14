from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from corehq.motech.repeaters.models import Repeater


class Command(BaseCommand):
    help = f"""
    Manages Repeater configuration including max_workers and backoff
    codes.

    Options:
    --set-max-workers: Number of Celery workers allocated to sending a
        batch of repeat records. Set to "0" to use the default
        ({settings.DEFAULT_REPEATER_WORKERS}). Set to "1" to send repeat
        records chronologically, one at a time. The maximum value is
        {settings.MAX_REPEATER_WORKERS}.
    --add-backoff-code: Adds HTTP status code to incl_backoff_codes list
    --remove-backoff-code: Removes HTTP status code from
        excl_backoff_codes list

    If no optional arguments are provided, displays current values for
    all properties.

    Usage examples:
    # Display current values
    python manage.py repeater <domain_name> <repeater_id>

    # Set max_workers
    python manage.py repeater <domain_name> <repeater_id> --set-max-workers 5

    # Add backoff code
    python manage.py repeater <domain_name> <repeater_id> --add-backoff-code 404

    # Remove backoff code
    python manage.py repeater <domain_name> <repeater_id> --remove-backoff-code 502
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('repeater_id')
        parser.add_argument('--set-max-workers', type=int,
                          help='Set number of Celery workers for this repeater')
        parser.add_argument('--add-backoff-code', type=int,
                          help='Add HTTP status code to incl_backoff_codes')
        parser.add_argument('--remove-backoff-code', type=int,
                          help='Remove HTTP status code from excl_backoff_codes')

    def _get_repeater(self, domain, repeater_id):
        try:
            return Repeater.objects.get(domain=domain, id=repeater_id)
        except Repeater.DoesNotExist:
            raise CommandError(
                f'Repeater {repeater_id} was not found in domain {domain}.'
            )

    def _get_repeater_info(self, repeater):
        self.stdout.write(f'max_workers: {repeater.max_workers}')
        self.stdout.write(f'incl_backoff_codes: {repeater.incl_backoff_codes}')
        self.stdout.write(f'excl_backoff_codes: {repeater.excl_backoff_codes}')

    def _set_max_workers(self, repeater, max_workers):
        if not 0 <= max_workers <= settings.MAX_REPEATER_WORKERS:
            self.stderr.write(
                'max_workers must be between 0 and '
                f'{settings.MAX_REPEATER_WORKERS}.'
            )
            return

        # Use `update_fields` to avoid a conflict if Celery is also
        # updating the repeater.
        repeater.max_workers = max_workers
        repeater.save(update_fields=['max_workers'])

    def handle(self, domain, repeater_id, *args, **options):
        set_max_workers = options.get('set_max_workers')
        add_backoff_code = options.get('add_backoff_code')
        remove_backoff_code = options.get('remove_backoff_code')

        repeater = self._get_repeater(domain, repeater_id)
        if set_max_workers is not None:
            self._set_max_workers(repeater, set_max_workers)
        if add_backoff_code is not None:
            repeater.add_backoff_code(add_backoff_code)
        if remove_backoff_code is not None:
            repeater.remove_backoff_code(remove_backoff_code)
        self._get_repeater_info(repeater)
