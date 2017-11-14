from __future__ import absolute_import
from celery.task import task
from corehq.pillows.case_search import delete_case_search_cases, \
    CaseSearchReindexerFactory


@task
def reindex_case_search_for_domain(domain):
    CaseSearchReindexerFactory(domain=domain).build().reindex()


@task
def delete_case_search_cases_for_domain(domain):
    delete_case_search_cases(domain)
