
import logging

from django.core.management import BaseCommand

from corehq.apps.domain.utils import silence_during_tests
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked
from six.moves import input

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

        logger.info('Hard deleting forms...')
        deleted_sql_form_ids = FormAccessorSQL.get_deleted_form_ids_in_domain(domain)
        for form_id_chunk in chunked(with_progress_bar(deleted_sql_form_ids, stream=silence_during_tests()), 500):
            FormAccessorSQL.hard_delete_forms(domain, list(form_id_chunk), delete_attachments=True)

        logger.info('Hard deleting cases...')
        deleted_sql_case_ids = CaseAccessorSQL.get_deleted_case_ids_in_domain(domain)
        for case_id_chunk in chunked(with_progress_bar(deleted_sql_case_ids, stream=silence_during_tests()), 500):
            CaseAccessorSQL.hard_delete_cases(domain, list(case_id_chunk))

        logger.info('Done.')
