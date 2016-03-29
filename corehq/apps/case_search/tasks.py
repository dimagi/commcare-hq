from celery.task import task
from corehq.pillows.case_search import get_couch_case_search_reindexer


@task
def reindex_case_search_for_domain(domain):
    get_couch_case_search_reindexer(domain).reindex()


@task
def delete_case_search_cases_for_domain(domain):
    pass
