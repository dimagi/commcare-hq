from collections import defaultdict, namedtuple
from datetime import datetime, timedelta

from dimagi.utils.chunked import chunked
from dimagi.utils.parsing import string_to_datetime

from corehq.apps.es import (
    CaseES,
    CaseSearchES,
    FormES,
    GroupES,
    UserES,
    aggregations,
    filters,
)
from corehq.apps.es.aggregations import (
    MISSING_KEY,
    ExtendedStatsAggregation,
    MissingAggregation,
    TermsAggregation,
    TopHitsAggregation,
)
from corehq.apps.es.cases import case_type as case_type_filter
from corehq.apps.es.cases import closed_range as closed_range_filter
from corehq.apps.es.forms import completed as completed_filter
from corehq.apps.es.forms import submitted as submitted_filter
from corehq.apps.es.forms import xmlns as xmlns_filter
from corehq.apps.export.const import (
    CASE_SCROLL_SIZE,
    MAX_MULTIMEDIA_EXPORT_SIZE,
)
from corehq.apps.hqcase.utils import SYSTEM_FORM_XMLNS_MAP
from corehq.elastic import ES_DEFAULT_INSTANCE, ES_EXPORT_INSTANCE
from corehq.util.quickcache import quickcache

PagedResult = namedtuple('PagedResult', 'total hits')


def get_last_submission_time_for_users(domain, user_ids, datespan, es_instance_alias=ES_DEFAULT_INSTANCE):
    def convert_to_date(date):
        return string_to_datetime(date).date() if date else None
    query = (
        FormES(es_instance_alias=es_instance_alias)
        .domain(domain)
        .user_id(user_ids)
        .completed(gte=datespan.startdate.date(), lte=datespan.enddate.date())
        .aggregation(
            TermsAggregation('user_id', 'form.meta.userID').aggregation(
                TopHitsAggregation(
                    'top_hits_last_form_submissions',
                    'form.meta.timeEnd',
                    is_ascending=False,
                    include='form.meta.timeEnd',
                )
            )
        )
        .size(0)
    )

    aggregations = query.run().aggregations
    buckets_dict = aggregations.user_id.buckets_dict
    result = {}
    for user_id, bucket in buckets_dict.items():
        result[user_id] = convert_to_date(bucket.top_hits_last_form_submissions.hits[0]['form']['meta']['timeEnd'])
    return result


def get_active_case_counts_by_owner(domain, datespan, case_types=None, owner_ids=None, export=False):
    return _get_case_case_counts_by_owner(domain, datespan, case_types, False, owner_ids, export)


def get_total_case_counts_by_owner(domain, datespan, case_types=None, owner_ids=None, export=False):
    return _get_case_case_counts_by_owner(domain, datespan, case_types, True, owner_ids, export)


def _get_case_case_counts_by_owner(domain, datespan, case_types, is_total=False, owner_ids=None, export=False):
    es_instance = ES_EXPORT_INSTANCE if export else ES_DEFAULT_INSTANCE
    case_query = (CaseES(es_instance_alias=es_instance)
         .domain(domain)
         .opened_range(lte=datespan.enddate.date())
         .NOT(closed_range_filter(lt=datespan.startdate.date()))
         .terms_aggregation('owner_id', 'owner_id')
         .size(0))

    if case_types:
        case_query = case_query.filter({"terms": {"type.exact": case_types}})
    else:
        case_query = case_query.filter(filters.NOT(case_type_filter('commcare-user')))

    if not is_total:
        case_query = case_query.active_in_range(
            gte=datespan.startdate.date(),
            lte=datespan.enddate.date(),
        )

    if owner_ids:
        case_query = case_query.owner(owner_ids)

    return case_query.run().aggregations.owner_id.counts_by_bucket()


def get_case_counts_closed_by_user(domain, datespan, case_types=None, user_ids=None, export=False):
    return _get_case_counts_by_user(domain, datespan, case_types, False, user_ids, export)


def get_case_counts_opened_by_user(domain, datespan, case_types=None, user_ids=None, export=False):
    return _get_case_counts_by_user(domain, datespan, case_types, True, user_ids, export)


def _get_case_counts_by_user(domain, datespan, case_types=None, is_opened=True, user_ids=None, export=False):
    date_field = 'opened_on' if is_opened else 'closed_on'
    user_field = 'opened_by' if is_opened else 'closed_by'

    es_instance = ES_EXPORT_INSTANCE if export else ES_DEFAULT_INSTANCE
    case_query = (CaseES(es_instance_alias=es_instance)
        .domain(domain)
        .filter(
            filters.date_range(
                date_field,
                gte=datespan.startdate.date(),
                lte=datespan.enddate.date(),
            )
        )
        .terms_aggregation(user_field, 'by_user')
        .size(0))

    if case_types:
        case_query = case_query.case_type(case_types)
    else:
        case_query = case_query.filter(filters.NOT(case_type_filter('commcare-user')))

    if user_ids:
        case_query = case_query.filter(filters.term(user_field, user_ids))

    return case_query.run().aggregations.by_user.counts_by_bucket()


def get_paged_forms_by_type(
        domain,
        doc_types,
        sort_col=None,
        desc=True,
        start=0,
        size=10):
    sort_col = sort_col or "received_on"
    query = (
        FormES()
        .domain(domain)
        .remove_default_filter('is_xform_instance')
        .remove_default_filter('has_user')
        .doc_type([doc_type.lower() for doc_type in doc_types])
        .sort(sort_col, desc=desc)
        .start(start)
        .size(size)
    )
    result = query.run()
    return PagedResult(total=result.total, hits=result.hits)


@quickcache(['domain', 'xmlns'], timeout=14 * 24 * 60)
def guess_form_name_from_submissions_using_xmlns(domain, xmlns):
    return get_form_name_from_last_submission_for_xmlns(domain, xmlns)


def get_form_name_from_last_submission_for_xmlns(domain, xmlns):
    query = (
        FormES()
        .domain(domain)
        .xmlns(xmlns)
        .sort('received_on', desc=True)
        .source(['form.@name'])
        .size(1)
        .non_null('form.@name')
    )

    results = query.run().hits
    if results:
        return results[0]['form']['@name']
    return None


def get_username_in_last_form_user_id_submitted(domain, user_id):
    query = (
        FormES()
        .domain(domain)
        .user_id(user_id)
        .sort('received_on', desc=True)
        .source(['form.meta.username'])
        .size(1)
    )

    results = query.run().hits
    if results:
        return results[0]['form']['meta'].get('username', None)


def get_last_forms_by_app(user_id):
    """
    gets the last form submission for each app for a given user id
    :param user_id: id of a couch user
    :return: last form submission for every app that user has submitted
    """
    query = (
        FormES()
            .user_id(user_id)
            .aggregation(
            TermsAggregation('app_id', 'app_id').aggregation(
                TopHitsAggregation(
                    'top_hits_last_form_submissions',
                    'received_on',
                    is_ascending=False,
                )
            )
        )
        .size(0)
    )

    aggregations = query.run().aggregations

    buckets_dict = aggregations.app_id.buckets_dict
    result = []
    for app_id, bucket in buckets_dict.items():
        result.append(bucket.top_hits_last_form_submissions.hits[0])

    return result


def get_submission_counts_by_user(domain, datespan, user_ids=None, export=False):
    return _get_form_counts_by_user(domain, datespan, True, user_ids, export)


def get_completed_counts_by_user(domain, datespan, user_ids=None, export=False):
    return _get_form_counts_by_user(domain, datespan, False, user_ids, export)


def _get_form_counts_by_user(domain, datespan, is_submission_time, user_ids=None, export=False):
    es_instance = ES_EXPORT_INSTANCE if export else ES_DEFAULT_INSTANCE
    form_query = FormES(es_instance_alias=es_instance).domain(domain)
    for xmlns in SYSTEM_FORM_XMLNS_MAP.keys():
        form_query = form_query.filter(filters.NOT(xmlns_filter(xmlns)))

    if is_submission_time:
        form_query = (form_query
            .submitted(gte=datespan.startdate.date(),
                       lte=datespan.enddate.date()))
    else:
        form_query = (form_query
            .completed(gte=datespan.startdate.date(),
                       lte=datespan.enddate.date()))

    if user_ids:
        form_query = form_query.user_id(user_ids)

    form_query = (form_query
        .user_aggregation()
        .size(0))
    return form_query.run().aggregations.user.counts_by_bucket()


def get_submission_counts_by_date(domain, user_ids, datespan, timezone):
    return _get_form_counts_by_date(domain, user_ids, datespan, timezone, True)


def get_completed_counts_by_date(domain, user_ids, datespan, timezone):
    return _get_form_counts_by_date(domain, user_ids, datespan, timezone, False)


def _get_form_counts_by_date(domain, user_ids, datespan, timezone, is_submission_time):
    form_query = (FormES()
                  .domain(domain)
                  .user_id(user_ids))
    for xmlns in SYSTEM_FORM_XMLNS_MAP.keys():
        form_query = form_query.filter(filters.NOT(xmlns_filter(xmlns)))

    if is_submission_time:
        form_query = (form_query
            .submitted(gte=datespan.startdate.date(),
                     lte=datespan.enddate.date())
            .submitted_histogram(timezone.zone))

    else:
        form_query = (form_query
            .completed(gte=datespan.startdate.date(),
                     lte=datespan.enddate.date())
            .completed_histogram(timezone.zone))

    form_query = form_query.size(0)

    results = form_query.run().aggregations.date_histogram.buckets_list

    # Convert timestamp into timezone aware datetime. Must divide timestamp by 1000 since python's
    # fromtimestamp takes a timestamp in seconds, whereas elasticsearch's timestamp is in milliseconds
    results = list(map(
        lambda result:
            (datetime.fromtimestamp(result.key // 1000).date().isoformat(), result.doc_count),
        results,
    ))
    return dict(results)


def get_group_stubs(group_ids):
    return (GroupES()
        .group_ids(group_ids)
        .values('_id', 'name', 'case_sharing', 'reporting'))


def get_user_stubs(user_ids):
    from corehq.apps.reports.util import SimplifiedUserInfo
    return (UserES()
        .user_ids(user_ids)
        .show_inactive()
        .values(*SimplifiedUserInfo.ES_FIELDS))


def get_forms(domain, startdate, enddate, user_ids=None, app_ids=None, xmlnss=None, by_submission_time=True):

    date_filter_fn = submitted_filter if by_submission_time else completed_filter
    query = (
        FormES()
        .domain(domain)
        .filter(date_filter_fn(gte=startdate, lte=enddate))
        .app(app_ids)
        .xmlns(xmlnss)
        .size(5000)
    )

    if user_ids:
        query = (query
            .user_ids_handle_unknown(user_ids)
            .remove_default_filter('has_user'))

    result = query.run()
    return PagedResult(total=result.total, hits=result.hits)


def get_form_counts_by_user_xmlns(domain, startdate, enddate, user_ids=None,
                                  xmlnss=None, by_submission_time=True, export=False):

    missing_users = False

    date_filter_fn = submitted_filter if by_submission_time else completed_filter
    es_instance = ES_EXPORT_INSTANCE if export else ES_DEFAULT_INSTANCE
    query = (FormES(es_instance_alias=es_instance)
             .domain(domain)
             .filter(date_filter_fn(gte=startdate, lt=enddate))
             .aggregation(
                 TermsAggregation('user_id', 'form.meta.userID').aggregation(
                     TermsAggregation('app_id', 'app_id').aggregation(
                         TermsAggregation('xmlns', 'xmlns')
                     )
                 )
             )
             .size(0)
    )

    if user_ids:
        query = (query
            .user_ids_handle_unknown(user_ids)
            .remove_default_filter('has_user'))
        missing_users = None in user_ids
        if missing_users:
            query = query.aggregation(
                MissingAggregation('missing_user_id', 'form.meta.userID').aggregation(
                    TermsAggregation('app_id', 'app_id').aggregation(
                        TermsAggregation('xmlns', 'xmlns')
                    )
                )
            )

    if xmlnss:
        query = query.xmlns(xmlnss)

    counts = defaultdict(lambda: 0)
    aggregations = query.run().aggregations
    user_buckets = aggregations.user_id.buckets_list
    if missing_users:
        user_buckets.append(aggregations.missing_user_id.bucket)

    for user_bucket in user_buckets:
        app_buckets = user_bucket.app_id.buckets_list
        for app_bucket in app_buckets:
            xmlns_buckets = app_bucket.xmlns.buckets_list
            for xmlns_bucket in xmlns_buckets:
                key = (user_bucket.key, app_bucket.key, xmlns_bucket.key)
                counts[key] = xmlns_bucket.doc_count

    return counts


def get_form_duration_stats_by_user(
        domain,
        app_id,
        xmlns,
        user_ids,
        startdate,
        enddate,
        by_submission_time=True):
    """Gets stats on the duration of a selected form grouped by users"""
    date_filter_fn = submitted_filter if by_submission_time else completed_filter

    missing_users = None in user_ids

    query = (
        FormES()
        .domain(domain)
        .user_ids_handle_unknown(user_ids)
        .remove_default_filter('has_user')
        .xmlns(xmlns)
        .filter(date_filter_fn(gte=startdate, lt=enddate))
        .aggregation(
            TermsAggregation('user_id', 'form.meta.userID').aggregation(
                ExtendedStatsAggregation(
                    'duration_stats',
                    'form.meta.timeStart',
                    script="doc['form.meta.timeEnd'].value - doc['form.meta.timeStart'].value",
                )
            )
        )
        .size(0)
    )

    if app_id:
        query = query.app(app_id)

    if missing_users:
        query = query.aggregation(
            MissingAggregation('missing_user_id', 'form.meta.userID').aggregation(
                ExtendedStatsAggregation(
                    'duration_stats',
                    'form.meta.timeStart',
                    script="doc['form.meta.timeEnd'].value - doc['form.meta.timeStart'].value",
                )
            )
        )

    result = {}
    aggregations = query.run().aggregations

    if missing_users:
        result[MISSING_KEY] = aggregations.missing_user_id.bucket.duration_stats.result

    buckets_dict = aggregations.user_id.buckets_dict
    for user_id, bucket in buckets_dict.items():
        result[user_id] = bucket.duration_stats.result
    return result


def get_form_duration_stats_for_users(
        domain,
        app_id,
        xmlns,
        user_ids,
        startdate,
        enddate,
        by_submission_time=True):
    """Gets the form duration stats for a group of users"""
    date_filter_fn = submitted_filter if by_submission_time else completed_filter

    query = (
        FormES()
        .domain(domain)
        .user_ids_handle_unknown(user_ids)
        .remove_default_filter('has_user')
        .xmlns(xmlns)
        .filter(date_filter_fn(gte=startdate, lt=enddate))
        .aggregation(
            ExtendedStatsAggregation(
                'duration_stats',
                'form.meta.timeStart',
                script="doc['form.meta.timeEnd'].value - doc['form.meta.timeStart'].value",
            )
        )
        .size(0)
    )

    if app_id:
        query = query.app(app_id)

    return query.run().aggregations.duration_stats.result


def get_form_counts_for_domains(domains):
    return FormES() \
        .filter(filters.term('domain', domains)) \
        .domain_aggregation() \
        .size(0) \
        .run() \
        .aggregations.domain.counts_by_bucket()


def get_case_and_action_counts_for_domains(domains):
    actions_agg = aggregations.NestedAggregation('actions', 'actions')
    aggregation = aggregations.TermsAggregation('domain', 'domain').aggregation(actions_agg)
    results = CaseES() \
        .filter(filters.term('domain', domains)) \
        .aggregation(aggregation) \
        .size(0) \
        .run()

    domains_to_cases = results.aggregations.domain.buckets_dict

    def _domain_stats(domain_name):
        cases = domains_to_cases.get(domain_name, None)
        return {
            'cases': cases.doc_count if cases else 0,
            'case_actions': cases.actions.doc_count if cases else 0
        }

    return {
        domain: _domain_stats(domain)
        for domain in domains
    }


def get_form_ids_missing_from_elasticsearch(all_form_ids):
    missing_from_elasticsearch = set()
    for form_ids in chunked(all_form_ids, 500):
        form_ids = set(form_ids)
        not_missing = set(FormES().doc_id(form_ids).get_ids())
        missing_from_elasticsearch.update(form_ids - not_missing)
        assert not_missing - form_ids == set()
    return list(missing_from_elasticsearch)


def get_case_ids_missing_from_elasticsearch(all_case_ids):
    missing_from_elasticsearch = set()
    for case_ids in chunked(all_case_ids, 500):
        case_ids = set(case_ids)
        not_missing = set(CaseES().doc_id(case_ids).get_ids())
        missing_from_elasticsearch.update(case_ids - not_missing)
        assert not_missing - case_ids == set()
    return list(missing_from_elasticsearch)


def get_all_user_ids_submitted(domain, app_ids=None):
    query = (
        FormES()
        .domain(domain)
        .aggregation(
            TermsAggregation('user_id', 'form.meta.userID')
        )
        .size(0)
    )

    if app_ids:
        query = query.app(app_ids)

    return list(query.run().aggregations.user_id.buckets_dict)


def _forms_with_attachments(domain, app_id, xmlns, datespan, user_types):
    enddate = datespan.enddate + timedelta(days=1)
    query = (FormES()
             .domain(domain)
             .app(app_id)
             .xmlns(xmlns)
             .submitted(gte=datespan.startdate, lte=enddate)
             .remove_default_filter("has_user")
             .source(['_id', 'external_blobs']))

    if user_types:
        query = query.user_type(user_types)

    for form in query.scroll():
        try:
            for attachment in form.get('external_blobs', {}).values():
                if attachment['content_type'] != "text/xml":
                    yield form
                    continue
        except AttributeError:
            pass


def get_form_ids_having_multimedia(domain, app_id, xmlns, datespan, user_types):
    return {
        form['_id'] for form in _forms_with_attachments(domain, app_id, xmlns, datespan, user_types)
    }


def media_export_is_too_big(domain, app_id, xmlns, datespan, user_types):
    size = 0
    for form in _forms_with_attachments(domain, app_id, xmlns, datespan, user_types):
        for attachment in form.get('external_blobs', {}).values():
            size += attachment.get('content_length', 0)
            if size > MAX_MULTIMEDIA_EXPORT_SIZE:
                return True
    return False


def scroll_case_names(domain, case_ids):
    query = (CaseES()
            .domain(domain)
            .case_ids(case_ids)
            .source(['name', '_id'])
            .size(CASE_SCROLL_SIZE))
    return query.scroll()


@quickcache(['domain', 'use_case_search'], timeout=24 * 3600)
def get_case_types_for_domain_es(domain, use_case_search=False):
    index_class = CaseSearchES if use_case_search else CaseES
    query = (
        index_class().domain(domain).size(0)
        .terms_aggregation("type.exact", "case_types")
    )
    return set(query.run().aggregations.case_types.keys)


def get_case_search_types_for_domain_es(domain):
    return get_case_types_for_domain_es(domain, True)
