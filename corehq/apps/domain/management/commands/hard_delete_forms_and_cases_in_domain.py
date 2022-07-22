import logging

from django.core.management import BaseCommand

from ...deletion import delete_all_cases, delete_all_forms
from ...models import Domain

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
            '--allow-active-domain',
            action='store_true',
            dest='allow_active_domain',
            default=False,
            help='Override deleted domain check.',
        )

    def handle(self, domain, **options):
        domain_obj = Domain.get_by_name(domain)
        if not options['allow_active_domain'] and domain_obj and not domain_obj.doc_type.endswith('-Deleted'):
            print(f'WARNING: Domain {domain} is an active domain. If your intention is to delete the domain, you '
                  f'should use the `delete_domain` command instead. If you are sure you want to delete forms and'
                  f'cases for this domain, use the "--allow-active-domain" argument.')

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
