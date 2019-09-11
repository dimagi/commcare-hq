from collections import Counter
from datetime import date, timedelta
from django.db.models import Count

import dateutil
import six

from casexml.apps.case.models import CommCareCase
from couchforms.const import DEVICE_LOG_XMLNS
from couchforms.models import all_known_formlike_doc_types

from corehq.apps import es
from corehq.apps.domain.dbaccessors import (
    get_doc_count_in_domain_by_type,
    get_doc_ids_in_domain_by_type,
)
from corehq.apps.es import aggregations
from corehq.form_processor.backends.sql.dbaccessors import doc_type_to_state
from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.warehouse.models.facts import FormFact


def get_es_counts_by_doc_type(domain, es_indices=None, extra_filters=None):
    es_indices = es_indices or (es.CaseES, es.FormES, es.UserES, es.AppES, es.LedgerES, es.GroupES)
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
            return dateutil.parser.parse(result[0]['_source']['server_modified_on'])
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
    if should_use_sql_backend(domain):
        return _get_sql_forms_by_doc_type(domain, startdate, enddate)
    else:
        return _get_couch_forms_by_doc_type(domain)


def get_primary_db_form_ids(domain, doc_type, startdate, enddate):
    if should_use_sql_backend(domain):
        return get_sql_form_ids(domain, doc_type, startdate, enddate)
    else:
        # date filtering not supported for couch
        return set(get_doc_ids_in_domain_by_type(domain, doc_type, CommCareCase.get_db()))


def get_primary_db_case_counts(domain, startdate=None, enddate=None):
    if should_use_sql_backend(domain):
        return _get_sql_cases_by_doc_type(domain, startdate, enddate)
    else:
        return _get_couch_cases_by_doc_type(domain)


def get_primary_db_case_ids(domain, doc_type, startdate, enddate):
    if should_use_sql_backend(domain):
        return get_sql_case_ids(domain, doc_type, startdate, enddate)
    else:
        # date filtering not supported for couch
        return set(get_doc_ids_in_domain_by_type(domain, doc_type, CommCareCase.get_db()))


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


def _get_sql_forms_by_doc_type(domain, startdate=None, enddate=None):
    counter = Counter()
    for db_alias in get_db_aliases_for_partitioned_query():
        queryset = XFormInstanceSQL.objects.using(db_alias).filter(domain=domain)
        if startdate is not None:
            queryset = queryset.filter(received_on__gte=startdate)
        if enddate is not None:
            queryset = queryset.filter(received_on__lt=enddate)

        for doc_type, state in doc_type_to_state.items():
            counter[doc_type] += queryset.filter(state=state).count()

        where_clause = 'state & {0} = {0}'.format(XFormInstanceSQL.DELETED)
        counter['XFormInstance-Deleted'] += queryset.extra(where=[where_clause]).count()

    return counter


def _get_sql_cases_by_doc_type(domain, startdate=None, enddate=None):
    counter = Counter()
    for db_alias in get_db_aliases_for_partitioned_query():
        queryset = CommCareCaseSQL.objects.using(db_alias).filter(domain=domain)
        if startdate is not None:
            queryset = queryset.filter(server_modified_on__gte=startdate)
        if enddate is not None:
            queryset = queryset.filter(server_modified_on__lt=enddate)
        counter['CommCareCase'] += queryset.filter(deleted=False).count()
        counter['CommCareCase-Deleted'] += queryset.filter(deleted=True).count()

    return counter


def get_sql_case_ids(domain, doc_type, startdate, enddate):
    sql_ids = set()
    deleted = doc_type == 'CommCareCase-Deleted'
    for db_alias in get_db_aliases_for_partitioned_query():
        queryset = CommCareCaseSQL.objects.using(db_alias) \
            .filter(domain=domain, deleted=deleted)

        if startdate:
            queryset = queryset.filter(server_modified_on__gte=startdate)

        if enddate:
            queryset = queryset.filter(server_modified_on__lt=enddate)

        sql_ids.update(list(queryset.values_list('case_id', flat=True)))
    return sql_ids


def get_sql_form_ids(domain, doc_type, startdate, enddate):
    sql_ids = set()
    state = doc_type_to_state[doc_type]
    for db_alias in get_db_aliases_for_partitioned_query():
        queryset = XFormInstanceSQL.objects.using(db_alias) \
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
        return {"term": {
            "base_doc": "couchuser-deleted" if deleted else "couchuser"
        }}


def xform_counts_for_app_in_last_month(app):
    """
    Count number of submissions grouped by module, form in a given app.
    """
    last_month_end = date.today().replace(day=1) - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    result = FormFact.objects.filter(
        app_id=app._id, received_on__gte=last_month_start, received_on__lte=last_month_end
    ).values('xmlns').annotate(total=Count('xmlns'))
    count_by_xmlns = {x['xmlns']: x['total'] for x in result}
    ret = [('Module Name', 'Form Name', 'Number of forms')]
    for module in app.modules:
        for form in module.get_forms():
            ret.append((module.default_name(), form.default_name(), count_by_xmlns.pop(form.xmlns, 0)))
    for xmlns, count in six.iteritems(count_by_xmlns):
        ret.append(("Unknown module", xmlns, count))
    return ret
