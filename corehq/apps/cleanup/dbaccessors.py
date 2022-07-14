from collections import defaultdict

from django.db import connections

from corehq.apps.domain.models import Domain
from corehq.apps.es import AppES, CaseES, CaseSearchES, FormES, GroupES, UserES
from corehq.apps.userreports.util import (
    LEGACY_UCR_TABLE_PREFIX,
    UCR_TABLE_PREFIX,
    get_domain_for_ucr_table_name,
)
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.sql_db.connections import UCR_ENGINE_ID, ConnectionManager
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


def find_sql_forms_for_deleted_domains():
    form_count_by_deleted_domain = {}
    for domain in Domain.get_deleted_domain_names():
        form_count = 0
        for db_name in get_db_aliases_for_partitioned_query():
            form_count += XFormInstance.objects.using(db_name).filter(domain=domain).count()
        if form_count:
            form_count_by_deleted_domain[domain] = form_count

    return form_count_by_deleted_domain


def find_sql_cases_for_deleted_domains():
    case_count_by_deleted_domain = {}
    for domain in Domain.get_deleted_domain_names():
        case_count = 0
        for db_name in get_db_aliases_for_partitioned_query():
            case_count += CommCareCase.objects.using(db_name).filter(domain=domain).count()
        if case_count:
            case_count_by_deleted_domain[domain] = case_count

    return case_count_by_deleted_domain


def find_es_docs_for_deleted_domains():
    es_doc_counts_by_deleted_domain = defaultdict(dict)
    for domain in Domain.get_deleted_domain_names():
        for hqESQuery in [AppES, CaseES, CaseSearchES, FormES, GroupES, UserES]:
            query = hqESQuery().domain(domain)
            count = query.count()
            if count != 0:
                es_doc_counts_by_deleted_domain[domain][hqESQuery.index] = count

    return es_doc_counts_by_deleted_domain


def find_ucr_tables_for_deleted_domains():
    deleted_domain_names = Domain.get_deleted_domain_names()

    connection_name = ConnectionManager().get_django_db_alias(UCR_ENGINE_ID)
    table_names = connections[connection_name].introspection.table_names()
    ucr_table_names = [name for name in table_names if
                       name.startswith(UCR_TABLE_PREFIX) or name.startswith(LEGACY_UCR_TABLE_PREFIX)]

    deleted_domains_to_tables = defaultdict(list)

    for ucr_table_name in ucr_table_names:
        table_domain = get_domain_for_ucr_table_name(ucr_table_name)
        if table_domain in deleted_domain_names:
            deleted_domains_to_tables[table_domain].append(ucr_table_name)

    return deleted_domains_to_tables
