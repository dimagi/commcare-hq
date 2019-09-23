from django.core.management import BaseCommand

from dimagi.utils.chunked import chunked

from casexml.apps.case.models import CommCareCase
from corehq.doctypemigrations.continuous_migrate import bulk_get_revs


class Command(BaseCommand):
    """
    Republish case changes
            $ ./manage.py republish_couch_case_changes <DOMAIN> <case_ids.txt>
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_ids_file')

    def handle(self, domain, case_ids_file, *args, **options):
        self.domain = domain
        case_ids = self.get_case_ids(case_ids_file)
        self.publish_cases(domain, case_ids)

    def get_case_ids(self, case_ids_file):
        with open(case_ids_file, 'r') as f:
            lines = f.readlines()
            return [l.strip() for l in lines]

    def publish_cases(self, domain, case_ids):
        from corehq.apps.hqcase.management.commands.backfill_couch_forms_and_cases import (
            publish_change, create_case_change_meta)
        for ids in chunked(case_ids, 500):
            doc_id_rev_list = bulk_get_revs(CommCareCase.get_db(), ids)
            for doc_id, doc_rev in doc_id_rev_list:
                publish_change(
                    create_case_change_meta(domain, doc_id, doc_rev)
                )
