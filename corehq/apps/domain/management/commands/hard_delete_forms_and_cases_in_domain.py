from __future__ import absolute_import
from __future__ import unicode_literals

import logging

from django.core.management import BaseCommand

from corehq.apps.domain.utils import silence_during_tests
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        assert should_use_sql_backend(domain)

        logger.info('Hard deleting forms...')
        deleted_sql_form_ids = FormAccessorSQL.get_deleted_form_ids_in_domain(domain)
        for form_id_chunk in chunked(with_progress_bar(deleted_sql_form_ids, stream=silence_during_tests()), 500):
            FormAccessorSQL.hard_delete_forms(domain, list(form_id_chunk), delete_attachments=True)

        logger.info('Hard deleting cases...')
        deleted_sql_case_ids = CaseAccessorSQL.get_deleted_case_ids_in_domain(domain)
        for case_id_chunk in chunked(with_progress_bar(deleted_sql_case_ids, stream=silence_during_tests()), 500):
            CaseAccessorSQL.hard_delete_cases(domain, list(case_id_chunk))

        logger.info('Done.')
