from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator

from corehq.apps.domain.models import Domain
from corehq.toggles import DATA_MIGRATION


class Command(BaseCommand):
    help = (
        'Sets the redirect URL for a "302 Found" redirect response to app '
        'update requests from CommCare Mobile. Set the base URL only '
        '(e.g. "https://example.com/"). THIS FEATURE ASSUMES THAT THE DOMAIN '
        'WAS MIGRATED FROM THIS ENVIRONMENT TO THE TARGET ENVIRONMENT: Domain '
        'names must match; App IDs must match; User IDs must match.'
    )

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--set',
            help="The base URL to redirect to",
        )
        parser.add_argument(
            '--unset',
            help="Remove the current redirect",
            action='store_true',
        )

    def handle(self, domain, **options):
        domain_obj = Domain.get_by_name(domain)

        if options['set']:
            _assert_data_migration(domain)
            url = options['set']
            _assert_valid_url(url)
            domain_obj.redirect_url = url
            domain_obj.save()

        elif options['unset']:
            domain_obj.redirect_url = ''
            domain_obj.save()

        if domain_obj.redirect_url:
            self.stdout.write(
                f'App updates are redirected to {domain_obj.redirect_url}'
            )
        else:
            self.stdout.write('Redirect URL not set')


def _assert_data_migration(domain):
    if not DATA_MIGRATION.enabled(domain):
        raise CommandError(f'Domain {domain} is not migrated.')


def _assert_valid_url(url):
    if not url.startswith('https'):
        raise CommandError(f'{url} is not a secure URL.')

    validate = URLValidator()
    try:
        validate(url)
    except ValidationError:
        raise CommandError(f'{url} is not a valid URL.')
