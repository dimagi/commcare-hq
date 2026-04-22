from corehq.apps.celery import task
from corehq.pillows.case_search import CaseSearchReindexerFactory


@task
def reindex_case_search_for_domain(domain):
    CaseSearchReindexerFactory(domain=domain).build().reindex()
