from celery import shared_task

from corehq.pillows.case_search import (
    CaseSearchReindexerFactory,
    delete_case_search_cases,
)


@shared_task
def reindex_case_search_for_domain(domain):
    CaseSearchReindexerFactory(domain=domain).build().reindex()


@shared_task
def delete_case_search_cases_for_domain(domain):
    delete_case_search_cases(domain)
