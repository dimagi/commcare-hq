from __future__ import absolute_import
from __future__ import unicode_literals
from celery.task import task
from corehq.pillows.case_search import delete_case_search_cases, \
    CaseSearchReindexerFactory


@task(serializer='pickle')
def reindex_case_search_for_domain(domain):
    reindex_case_search_for_domain_json_args(domain)


@task
def reindex_case_search_for_domain_json_args(domain):
    CaseSearchReindexerFactory(domain=domain).build().reindex()


@task(serializer='pickle')
def delete_case_search_cases_for_domain(domain):
    delete_case_search_cases_for_domain_json_args(domain)


@task
def delete_case_search_cases_for_domain_json_args(domain):
    delete_case_search_cases(domain)
