import datetime

from dimagi.utils.dates import add_months

from corehq.apps.data_analytics.const import DEFAULT_EXPERIENCED_THRESHOLD
from corehq.apps.es.aggregations import (
    AggregationTerm,
    NestedTermAggregationsHelper,
    TermsAggregation,
)
from corehq.apps.es.forms import FormES
from corehq.apps.es.sms import SMSES
from corehq.apps.es.users import UserES


def get_app_submission_breakdown_es(domain_name, monthspan, user_ids=None):
    # takes > 1 m to load at 50k worker scale
    terms = [
        AggregationTerm('app_id', 'app_id'),
        AggregationTerm('device_id', 'form.meta.deviceID'),
        AggregationTerm('user_id', 'form.meta.userID'),
    ]
    query = FormES(for_export=True).domain(domain_name).submitted(
        gte=monthspan.startdate,
        lt=monthspan.computed_enddate,
    )
    if user_ids is not None:
        query = query.user_id(user_ids)
    return NestedTermAggregationsHelper(base_query=query, terms=terms).get_data()


def get_domain_device_breakdown_es(domain_name, monthspan):
    query = FormES(for_export=True).domain(domain_name).submitted(
        gte=monthspan.startdate,
        lt=monthspan.computed_enddate,
    ).aggregation(TermsAggregation('device_id', 'form.meta.deviceID')).size(0)

    return query.run().aggregations.device_id.counts_by_bucket()


def get_mobile_users(domains):
    return set(
        UserES()
        .mobile_users()
        .domain(domains, include_inactive=True)
        .scroll_ids()
    )


def active_mobile_users(domain, start, end, *args):
    """
    Returns the number of mobile users who have submitted a form or SMS in the
    time specified
    """

    user_ids = get_mobile_users(domain.name)

    form_users = (FormES(for_export=True)
                  .domain(domain.name)
                  .user_aggregation()
                  .submitted(gte=start, lt=end)
                  .user_id(user_ids)
                  .size(0)
                  .run()
                  .aggregations.user.counts_by_bucket())

    sms_users = set(
        SMSES(for_export=True)
        .incoming_messages()
        .user_aggregation()
        .to_commcare_user()
        .domain(domain.name)
        .received(gte=start, lt=end)
        .size(0)
        .run()
        .aggregations.user.keys
    )

    return set(user_ids), form_users, sms_users


def get_forms_for_users(domain, user_ids, start, end):
    query = (
        FormES(for_export=True)
        .domain(domain)
        .submitted(gte=start, lte=end)
        .user_id(user_ids)
        .source(['form.meta.userID', 'form.case', 'form.@xmlns'])
    )

    return query.scroll()


def get_possibly_experienced(domain, start):

    user_ids = get_mobile_users(domain.name)
    threshold = domain.internal.experienced_threshold or DEFAULT_EXPERIENCED_THRESHOLD
    months = threshold - 2
    threshold_month = add_months(start.startdate.year, start.startdate.month, -months)
    end_month = datetime.date(day=1, year=threshold_month[0], month=threshold_month[1])

    form_users = set(
        FormES(for_export=True)
        .domain(domain.name)
        .user_aggregation()
        .submitted(lt=end_month)
        .user_id(user_ids)
        .size(0)
        .run()
        .aggregations.user.keys
    )

    return set(form_users)
