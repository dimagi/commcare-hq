from collections import Counter

import dateutil

from couchforms.const import DEVICE_LOG_XMLNS

from corehq.apps import es
from corehq.apps.es import aggregations
from corehq.form_processor.backends.sql.dbaccessors import doc_type_to_state
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


def get_es_counts_by_doc_type(domain, es_indices=None, extra_filters=None):
    es_indices = es_indices or (es.CaseES, es.FormES, es.UserES, es.AppES, es.GroupES)
    counter = Counter()
    for es_query in es_indices:
        counter += get_index_counts_by_domain_doc_type(es_query, domain, extra_filters)

    return counter


def get_es_case_counts(domain, doc_type, gte, lt):
    ex = es.cases.server_modified_range(gte=gte, lt=lt)
    return es.cases.CaseES().domain(domain).filter(ex).filter(
        es.filters.OR(
            es.filters.doc_type(doc_type),
            es.filters.doc_type(doc_type.lower()),
        )
    ).count()


def get_es_case_range(domain):
    def descending_query(order):
        result = es.CaseES().domain(domain).sort(
            'server_modified_on', desc=order).size(1).run().raw_hits
        if len(result) == 0:
            return None
        else:
            return dateutil.parser.parse(result[0]['_source']['server_modified_on']).date()
    return (
        descending_query(order=False),
        descending_query(order=True)
    )


def get_index_counts_by_domain_doc_type(es_query_class, domain, extra_filters=None):
    """
    :param es_query_class: Subclass of ``HQESQuery``
    :param domain: Domain name to filter on
    :returns: Counter of document counts per doc_type in the ES Index
    """
    query = (
        es_query_class()
        .remove_default_filters()
        .filter(es.users.domain(domain))
        .terms_aggregation('doc_type', 'doc_type')
        .size(0))

    if extra_filters is not None:
        for extra_filter in extra_filters:
            query = query.filter(extra_filter)

    return Counter(query.run().aggregations.doc_type.counts_by_bucket())


def get_es_user_counts_by_doc_type(domain):
    agg = aggregations.TermsAggregation('doc_type', 'doc_type').aggregation(
        aggregations.TermsAggregation('base_doc', 'base_doc')
    )
    doc_type_buckets = (
        es.UserES()
        .remove_default_filters()
        .filter(es.users.domain(domain))
        .aggregation(agg)
        .size(0)
        .run()
        .aggregations.doc_type.buckets_dict
    )
    counts = Counter()
    for doc_type, bucket in doc_type_buckets.items():
        for base_doc, count in bucket.base_doc.counts_by_bucket().items():
            deleted = base_doc.endswith('deleted')
            if deleted:
                doc_type += '-Deleted'
            counts[doc_type] = count

    return counts


def get_primary_db_form_counts(domain, startdate=None, enddate=None):
    counter = Counter()
    for db_alias in get_db_aliases_for_partitioned_query():
        queryset = XFormInstance.objects.using(db_alias).filter(domain=domain)
        if startdate is not None:
            queryset = queryset.filter(received_on__gte=startdate)
        if enddate is not None:
            queryset = queryset.filter(received_on__lt=enddate)

        for doc_type, state in doc_type_to_state.items():
            counter[doc_type] += queryset.filter(state=state).count()

        where_clause = 'deleted_on IS NOT NULL'
        counter['XFormInstance-Deleted'] += queryset.extra(where=[where_clause]).count()

    return counter


def get_primary_db_case_counts(domain, startdate=None, enddate=None):
    counter = Counter()
    for db_alias in get_db_aliases_for_partitioned_query():
        queryset = CommCareCase.objects.using(db_alias).filter(domain=domain)
        if startdate is not None:
            queryset = queryset.filter(server_modified_on__gte=startdate)
        if enddate is not None:
            queryset = queryset.filter(server_modified_on__lt=enddate)
        counter['CommCareCase'] += queryset.filter(deleted=False).count()
        counter['CommCareCase-Deleted'] += queryset.filter(deleted=True).count()

    return counter


def get_primary_db_case_ids(domain, doc_type, startdate, enddate):
    sql_ids = set()
    deleted = doc_type == 'CommCareCase-Deleted'
    for db_alias in get_db_aliases_for_partitioned_query():
        queryset = CommCareCase.objects.using(db_alias) \
            .filter(domain=domain, deleted=deleted)

        if startdate:
            queryset = queryset.filter(server_modified_on__gte=startdate)

        if enddate:
            queryset = queryset.filter(server_modified_on__lt=enddate)

        sql_ids.update(list(queryset.values_list('case_id', flat=True)))
    return sql_ids


def get_primary_db_form_ids(domain, doc_type, startdate, enddate):
    sql_ids = set()
    state = doc_type_to_state[doc_type]
    for db_alias in get_db_aliases_for_partitioned_query():
        queryset = XFormInstance.objects.using(db_alias) \
            .filter(domain=domain, state=state) \
            .exclude(xmlns=DEVICE_LOG_XMLNS)

        if startdate:
            queryset = queryset.filter(received_on__gte=startdate)

        if enddate:
            queryset = queryset.filter(received_on__lt=enddate)

        sql_ids.update(list(queryset.values_list('form_id', flat=True)))
    return sql_ids


def get_es_case_ids(domain, doc_type, startdate, enddate):
    datefilter = None
    if startdate or enddate:
        datefilter = es.cases.server_modified_range(gte=startdate, lt=enddate)
    return _get_es_doc_ids(es.CaseES, domain, doc_type, datefilter)


def get_es_form_ids(domain, doc_type, startdate, enddate):
    datefilter = None
    if startdate or enddate:
        datefilter = es.forms.submitted(gte=startdate, lt=enddate)
    return _get_es_doc_ids(es.FormES, domain, doc_type, datefilter)


def _get_es_doc_ids(es_query_class, domain, doc_type, datefilter=None):
    query = (
        es_query_class()
        .remove_default_filters()
        .filter(es.filters.domain(domain))
        .filter(es.filters.OR(
            es.filters.doc_type(doc_type),
            es.filters.doc_type(doc_type.lower()),
        )).exclude_source()
    )
    if datefilter:
        query = query.filter(datefilter)

    return set(query.scroll())


def get_es_user_ids(domain, doc_type):
    return set(
        es.UserES()
        .remove_default_filters()
        .filter(es.users.domain(domain))
        .filter(es.filters.doc_type(doc_type))
        .filter(_get_user_base_doc_filter(doc_type))
        .get_ids()
    )


def _get_user_base_doc_filter(doc_type):
    deleted = 'Deleted' in doc_type
    if deleted:
        doc_type = doc_type[:-1]

    if doc_type == 'CommCareUser':
        return es.filters.term("base_doc", "couchuser-deleted" if deleted else "couchuser")
