import logging

from django.core.management import BaseCommand

from .delete_domain import Command as delete_domain

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

    def handle(self, domain, **options):
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

        delete_domain.hard_delete_cases(domain)
        delete_domain.hard_delete_forms(domain)
        logger.info('Done.')
