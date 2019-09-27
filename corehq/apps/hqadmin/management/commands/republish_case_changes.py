from django.core.management import BaseCommand

from corehq.form_processor.utils import should_use_sql_backend
from dimagi.utils.chunked import chunked

from casexml.apps.case.models import CommCareCase
from corehq.doctypemigrations.continuous_migrate import bulk_get_revs


class Command(BaseCommand):
    """
    Republish case changes. Meant to be used in conjunction with stale_cases_in_es command
            $ ./manage.py republish_couch_case_changes <DOMAIN> <case_ids.txt>
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_ids_file')

    def handle(self, domain, case_ids_file, *args, **options):
        case_ids = _get_case_ids(case_ids_file)
        _publish_cases(domain, case_ids)


def _get_case_ids(case_ids_file):
    with open(case_ids_file, 'r') as f:
        lines = f.readlines()
        return [l.split(',')[0].strip() for l in lines]


def _publish_cases(self, domain, case_ids):
    if should_use_sql_backend(domain):
        _publish_cases_for_couch(domain, case_ids)
    else:
        _publish_cases_for_sql(domain, case_ids)


def _publish_cases_for_couch(domain, case_ids):
    from corehq.apps.hqcase.management.commands.backfill_couch_forms_and_cases import (
        publish_change, create_case_change_meta)
    for ids in chunked(case_ids, 500):
        doc_id_rev_list = bulk_get_revs(CommCareCase.get_db(), ids)
        for doc_id, doc_rev in doc_id_rev_list:
            publish_change(
                create_case_change_meta(domain, doc_id, doc_rev)
            )


def _publish_cases_for_sql(domain, case_ids):
    print('sql domains not supported yet')


