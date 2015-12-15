from datetime import datetime

from corehq.apps.es import FormES, UserES, GroupES
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
