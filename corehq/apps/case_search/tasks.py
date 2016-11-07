from corehq.pillows.case_search import delete_case_search_cases, \
    get_case_search_reindexer
from corehq.util.celery_utils import hqtask


@hqtask()
def reindex_case_search_for_domain(domain):
    get_case_search_reindexer(domain).reindex()


@hqtask()
def delete_case_search_cases_for_domain(domain):
    delete_case_search_cases(domain)
