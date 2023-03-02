import logging

from django.core.management import BaseCommand

from ...deletion import delete_all_cases, delete_all_forms
from ...utils import is_domain_in_use

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            default=False,
            help='Skip important confirmation warnings.',
        )
        parser.add_argument(
            '--ignore-domain-in-use',
            action='store_true',
            dest='ignore_domain_in_use',
            default=False,
            help='Allow deleting forms and cases for a domain that is in use.',
        )

    def handle(self, domain, **options):
        if not options['ignore_domain_in_use'] and is_domain_in_use(domain):
            print(f'WARNING: Domain {domain} is currently in use. If your intention is to delete the domain, you '
                  f'should use the `delete_domain` command instead. If you are sure you want to delete forms and'
                  f'cases for this domain, use the "--ignore-domain-in-use" argument.')
            return

        if not options['noinput']:
            confirm = input(
                """
                Are you sure you want to hard delete all forms and cases in domain "{}"?
                This operation is PERMANENT.

                Type the domain's name again to continue, or anything else to cancel:
                """.format(domain)
            )
            if confirm != domain:
                print("\n\t\tDomain deletion cancelled.")
                return

        delete_all_cases(domain)
        delete_all_forms(domain)
        logger.info('Done.')
