from django.core.management.base import BaseCommand

from corehq.apps.es import CaseES, CaseSearchES, case_adapter
from corehq.form_processor.models.cases import CommCareCase, RebuildWithReason
from corehq.form_processor.backends.sql.processor import FormProcessorSQL


class Command(BaseCommand):
    help = ('Remove cases from case index in elasticsearch if deleted')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--dry-run', action="store_true")

    def handle(self, domain, **options):
        dry_run = options["dry_run"]
        missing_case_ids = get_case_ids_missing_from_case_search(domain)
        for case_id in missing_case_ids:
            should_delete = should_case_be_deleted(case_id, domain)
            if should_delete:
                print(f"removing case {case_id} in domain {domain} from ES")
                if not dry_run:
                    case_adapter.delete(case_id, refresh=True)
            else:
                print(f"case {case_id} in domain {domain} is not deleted")


def should_case_be_deleted(case_id, domain):
    """
    This rebuilds a case from its related forms to determine what state the case
    should be in
    :param case_id: case_id for CommCareCase
    :param domain: domain name
    :return: returns True if it is in the deleted state, and False otherwise
    """
    detail = RebuildWithReason(reason="check final state of case")
    sql_case, lock_obj = FormProcessorSQL.get_case_with_lock(case_id, lock=False)
    if not sql_case:
        sql_case = CommCareCase(case_id=case_id, domain=domain)
    commcare_case, rebuild_transaction = FormProcessorSQL._rebuild_case_from_transactions(sql_case, detail)
    return commcare_case.is_deleted


def get_case_ids_missing_from_case_search(domain):
    """
    Finds discrepancies between the Case and CaseSearch indices in Elasticsearch
    :param domain: domain name
    :return: list of case ids that exist in Case index but not CaseSearch index
    """
    case_ids_in_es = set([c['_id'] for c in list(CaseES().domain(domain).scroll())])
    case_search_ids_in_es = set([c['_id'] for c in list(CaseSearchES().domain(domain).scroll())])
    return list(case_ids_in_es - case_search_ids_in_es)
