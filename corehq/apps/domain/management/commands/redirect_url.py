from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.domain.models import DomainSettings


class Command(BaseCommand):
    help = (
        'Sets the redirect URL for a "308 Permanent Redirect" response to '
        'form submissions and syncs. Only valid for domains that have been '
        'migrated to new environments. Set the schema and hostname only '
        '(e.g. "https://example.com/"). The rest of the path will be appended '
        'for redirecting different endpoints. THIS FEATURE ASSUMES THE DOMAIN '
        'NAME IS THE SAME ON BOTH ENVIRONMENTS.'
    )

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--set',
            help="The URL to redirect to",
        )
        parser.add_argument(
            '--unset',
            help="Remove the current redirect",
            action='store_true',
        )

    def handle(self, domain, **options):
        domain_settings, _ = DomainSettings.objects.get_or_create(pk=domain)

        if options['set']:
            domain_settings.redirect_base_url = options['set']
            try:
                domain_settings.clean_fields()
                domain_settings.clean()
            except ValidationError as err:
                msg = err.error_dict['redirect_base_url'][0].message
                raise CommandError(msg)
            domain_settings.save()

        elif options['unset']:
            domain_settings.redirect_base_url = ''
            domain_settings.save()

        if domain_settings.redirect_base_url:
            self.stdout.write(
                'Form submissions and syncs are redirected to '
                f'{domain_settings.redirect_base_url}'
            )
        else:
            self.stdout.write('Redirect URL not set')
