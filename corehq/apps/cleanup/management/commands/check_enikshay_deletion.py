from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import itertools

from django.core.management import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.es import AppES, CaseES, CaseSearchES, DomainES, FormES, GroupES, LedgerES, UserES
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, doc_type_to_state, FormAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors

DOMAINS = (
    'enikshay-test',
    'enikshay',
    'enikshay-test-2',
    'enikshay-test-3',
    'enikshay-nikshay-migration-test',
    'enikshay-domain-copy-test',
    'enikshay-aks-audit',
    'np-migration-3',
    'enikshay-uatbc-migration-test-1',
    'enikshay-uatbc-migration-test-2',
    'enikshay-uatbc-migration-test-3',
    'enikshay-uatbc-migration-test-4',
    'enikshay-uatbc-migration-test-5',
    'enikshay-uatbc-migration-test-6',
    'enikshay-uatbc-migration-test-7',
    'enikshay-uatbc-migration-test-8',
    'enikshay-uatbc-migration-test-9',
    'enikshay-uatbc-migration-test-10',
    'enikshay-uatbc-migration-test-11',
    'enikshay-uatbc-migration-test-12',
    'enikshay-uatbc-migration-test-13',
    'enikshay-uatbc-migration-test-14',
    'enikshay-uatbc-migration-test-15',
    'enikshay-uatbc-migration-test-16',
    'enikshay-uatbc-migration-test-17',
    'enikshay-uatbc-migration-test-18',
    'enikshay-uatbc-migration-test-19',
    'sheel-enikshay',
    'enikshay-reports-qa',
    'enikshay-performance-test',
)


class Command(BaseCommand):

    def handle(self, **options):
        for domain_name in DOMAINS:
            if not any(check(domain_name) for check in [
                _check_domain_exists,
                _check_cases,
                _check_soft_deleted_sql_cases,
                _check_forms,
                _check_soft_deleted_sql_forms,
                _check_elasticsearch,
            ]):
                print('No remaining data for domain "%s"' % domain_name)


def _check_domain_exists(domain_name):
    domain = Domain.get_by_name(domain_name)
    if domain:
        print('Domain "%s" still exists.' % domain_name)
        return True


def _check_cases(domain_name):
    case_accessor = CaseAccessors(domain_name)
    case_ids = case_accessor.get_case_ids_in_domain()
    if case_ids:
        print('Domain "%s" contains %s cases.' % (domain_name, len(case_ids)))
        return True


def _check_soft_deleted_sql_cases(domain_name):
    soft_deleted_case_ids = CaseAccessorSQL.get_deleted_case_ids_in_domain(domain_name)
    if soft_deleted_case_ids:
        print('Domain "%s" contains %s soft-deleted SQL cases.' % (domain_name, len(soft_deleted_case_ids)))
        return True


def _check_forms(domain_name):
    form_accessor = FormAccessors(domain_name)
    form_ids = list(itertools.chain(*[
        form_accessor.get_all_form_ids_in_domain(doc_type=doc_type)
        for doc_type in doc_type_to_state
    ]))
    if form_ids:
        print('Domain "%s" contains %s forms.' % (domain_name, len(form_ids)))
        return True


def _check_soft_deleted_sql_forms(domain_name):
    soft_deleted_form_ids = FormAccessorSQL.get_deleted_form_ids_in_domain(domain_name)
    if soft_deleted_form_ids:
        print('Domain "%s" contains %s soft-deleted SQL forms.' % (domain_name, len(soft_deleted_form_ids)))
        return True


def _check_elasticsearch(domain_name):
    def _check_index(hqESQuery):
        if hqESQuery().domain(domain_name).run().total != 0:
            print('Domain "%s" contains data in ES index "%s"' % (domain_name, hqESQuery.index))
            return True

    return any(_check_index(hqESQuery) for hqESQuery in [
        AppES, CaseES, CaseSearchES, DomainES, FormES, GroupES, LedgerES, UserES
    ])
