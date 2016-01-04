from datetime import datetime

from corehq.apps.es import FormES, UserES, GroupES, CaseES, filters
from corehq.apps.es.cases import closed_range
from dimagi.utils.parsing import string_to_datetime


def get_last_submission_time_for_user(domain, user_id, datespan):
    form_query = FormES() \
        .domain(domain) \
        .user_id([user_id]) \
        .completed(gte=datespan.startdate.date(), lte=datespan.enddate.date()) \
        .sort("form.meta.timeEnd", desc=True) \
        .size(1)
    results = form_query.run().raw_hits

    def convert_to_date(date):
        return string_to_datetime(date).date() if date else None

    return convert_to_date(results[0]['_source']['form']['meta']['timeEnd'] if results else None)


def get_active_case_counts_by_owner(domain, datespan, case_types=None):
    return _get_case_case_counts_by_owner(domain, datespan, case_types, False)


def get_total_case_counts_by_owner(domain, datespan, case_types=None):
    return _get_case_case_counts_by_owner(domain, datespan, case_types, True)


def _get_case_case_counts_by_owner(domain, datespan, case_types, is_total=False):
    case_query = (CaseES()
         .domain(domain)
         .opened_range(lte=datespan.enddate)
         .NOT(closed_range(lt=datespan.startdate))
         .terms_facet('owner_id', 'owner_id')
         .size(0))

    if case_types:
        case_query = case_query.filter({"terms": {"type.exact": case_types}})

    if not is_total:
        case_query = case_query.active_in_range(
            gte=datespan.startdate,
            lte=datespan.enddate
        )

    return case_query.run().facets.owner_id.counts_by_term()


def get_case_counts_closed_by_user(domain, datespan, case_types=None):
    return _get_case_counts_by_user(domain, datespan, case_types, False)


def get_case_counts_opened_by_user(domain, datespan, case_types=None):
    return _get_case_counts_by_user(domain, datespan, case_types, True)


def _get_case_counts_by_user(domain, datespan, case_types=None, is_opened=True):
    date_field = 'opened_on' if is_opened else 'closed_on'
    user_field = 'opened_by' if is_opened else 'closed_by'

    case_query = (CaseES()
        .domain(domain)
        .filter(
            filters.date_range(
                date_field,
                gte=datespan.startdate.date(),
                lte=datespan.enddate.date(),
            )
        )
        .terms_facet(user_field, 'by_user', size=100000)
        .size(1))

    if case_types:
        case_query = case_query.filter({"terms": {"type.exact": case_types}})

    return case_query.run().facets.by_user.counts_by_term()


def get_submission_counts_by_user(domain, datespan):
    return _get_form_counts_by_user(domain, datespan, True)


def get_completed_counts_by_user(domain, datespan):
    return _get_form_counts_by_user(domain, datespan, False)


def _get_form_counts_by_user(domain, datespan, is_submission_time):
    form_query = FormES().domain(domain)

    if is_submission_time:
        form_query = (form_query
            .submitted(gte=datespan.startdate.date(),
                       lte=datespan.enddate.date()))
    else:
        form_query = (form_query
            .completed(gte=datespan.startdate.date(),
                       lte=datespan.enddate.date()))
    form_query = (form_query
        .user_facet()
        .size(1))
    return form_query.run().facets.user.counts_by_term()


def get_submission_counts_by_date(domain, user_ids, datespan, timezone):
    return _get_form_counts_by_date(domain, user_ids, datespan, timezone, True)


def get_completed_counts_by_date(domain, user_ids, datespan, timezone):
    return _get_form_counts_by_date(domain, user_ids, datespan, timezone, False)


def _get_form_counts_by_date(domain, user_ids, datespan, timezone, is_submission_time):
    form_query = (FormES()
                  .domain(domain)
                  .user_id(user_ids))

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

    form_query = form_query.size(1)

    results = form_query.run().facet('date_histogram', 'entries')
    # Convert timestamp into timezone aware dateime. Must divide timestamp by 1000 since python's
    # fromtimestamp takes a timestamp in seconds, whereas elasticsearch's timestamp is in milliseconds
    results = map(
        lambda result:
            (datetime.fromtimestamp(result['time'] / 1000, timezone).date().isoformat(), result['count']),
        results,
    )
    return dict(results)


def get_group_stubs(group_ids):
    return (GroupES()
        .group_ids(group_ids)
        .values(['_id', 'name', 'case_sharing', 'reporting']))


def get_user_stubs(user_ids):
    return (UserES()
        .user_ids(user_ids)
        .show_inactive()
        .values(['_id', 'username', 'first_name', 'last_name', 'doc_type', 'is_active']))
