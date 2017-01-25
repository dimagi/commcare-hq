from collections import Counter

from casexml.apps.case.models import CommCareCase
from corehq.apps import es
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_type
from corehq.apps.dump_reload.sql.dump import allow_form_processing_queries
from corehq.form_processor.backends.sql.dbaccessors import doc_type_to_state
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.sql_db.config import get_sql_db_aliases_in_use
from couchforms.models import all_known_formlike_doc_types


def get_es_form_counts(domain):
    return get_index_counts_by_domain_doc_type(es.FormES, domain)


def get_es_case_counts(domain):
    return get_index_counts_by_domain_doc_type(es.CaseES, domain)


def get_index_counts_by_domain_doc_type(es_query_class, domain):
    """
    :param es_query_class: Subclass of ``HQESQuery``
    :param domain: Domain name to filter on
    :returns: Counter of document counts per doc_type in the ES Index
    """
    return Counter(
        es_query_class()
        .remove_default_filters()
        .filter(es.filters.term('domain', domain))
        .terms_aggregation('doc_type', 'doc_type')
        .size(0)
        .run()
        .aggregations.doc_type.counts_by_bucket()
    )


def get_primary_db_form_counts(domain):
    if should_use_sql_backend(domain):
        return _get_sql_forms_by_doc_type(domain)
    else:
        return _get_couch_forms_by_doc_type(domain)


def get_primary_db_case_counts(domain):
    if should_use_sql_backend(domain):
        return _get_sql_cases_by_doc_type(domain)
    else:
        return _get_couch_cases_by_doc_type(domain)


def _get_couch_forms_by_doc_type(domain):
    return _get_couch_doc_counts(CommCareCase.get_db(), domain, all_known_formlike_doc_types())


def _get_couch_cases_by_doc_type(domain):
    return _get_couch_doc_counts(CommCareCase.get_db(), domain, ('CommCareCase', 'CommCareCase-Deleted'))


def _get_couch_doc_counts(couch_db, domain, doc_types):
    counter = Counter()
    for doc_type in doc_types:
        count = get_doc_count_in_domain_by_type(domain, doc_type, couch_db)
        counter.update({doc_type: count})
    return counter


@allow_form_processing_queries()
def _get_sql_forms_by_doc_type(domain):
    counter = Counter()
    for db_alias in get_sql_db_aliases_in_use():
        queryset = XFormInstanceSQL.objects.using(db_alias).filter(domain=domain)
        for doc_type, state in doc_type_to_state.items():
            counter[doc_type] += queryset.filter(state=state).count()

        where_clause = 'state & {0} = {0}'.format(XFormInstanceSQL.DELETED)
        counter['XFormInstance-Deleted'] += queryset.extra(where=[where_clause]).count()

    return counter


@allow_form_processing_queries()
def _get_sql_cases_by_doc_type(domain):
    counter = Counter()
    for db_alias in get_sql_db_aliases_in_use():
        queryset = CommCareCaseSQL.objects.using(db_alias).filter(domain=domain)
        counter['CommCareCase'] += queryset.filter(deleted=False).count()
        counter['CommCareCase-Deleted'] += queryset.filter(deleted=True).count()

    return counter
