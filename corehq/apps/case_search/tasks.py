from celery.task import task
from corehq.pillows.case_search import delete_case_search_cases, \
    get_case_search_reindexer


@task
def reindex_case_search_for_domain(domain):
    get_case_search_reindexer(domain).reindex()


@task
def delete_case_search_cases_for_domain(domain):
    delete_case_search_cases(domain)
