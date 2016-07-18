"""
Definitions for the graphs of admin reports.

Common params:
    domains: list of domains to search
    datespan: span of dates given from the UI to search
    interval: space between buckets (day, week, month, year)
    datefield: field to search the date (created_on, received etc)

Common Output:
    JSON with form:
        {
            startdate: [YYYY, MM, DD],
            enddate: [YYYY, MM, DD],
            initial_values: {
                label1: integer,
                label2: integer,
                ....
            },
            histo_data: {
                label1: [
                    {count: integer, time: time in milliseconds},
                        ....
                ],
                label2: [...],
                ....
            }
        }
"""
import datetime
from dateutil.relativedelta import relativedelta
from django.db.models import Q, Count
from django.utils.translation import ugettext as _

from corehq.apps.accounting.models import Subscription, SoftwarePlanEdition
from corehq.apps.commtrack.const import SUPPLY_POINT_CASE_TYPE
from corehq.apps.products.models import SQLProduct
from corehq.apps.domain.models import Domain
from corehq.apps.es.cases import CaseES
from corehq.apps.es.domains import DomainES
from corehq.apps.es.forms import FormES
from corehq.apps.es.sms import SMSES
from corehq.apps.es.users import UserES
from corehq.apps.groups.models import Group
from corehq.apps.hqadmin.reporting.exceptions import (
    HistoTypeNotFoundException,
    IntervalNotFoundException,
)
from corehq.apps.locations.models import SQLLocation
from corehq.elastic import (
    ADD_TO_ES_FILTER,
    DATE_FIELDS,
    es_histogram,
    ES_MAX_CLAUSE_COUNT,
    es_query,
)

from corehq.apps.sms.models import SQLMobileBackend
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.util.dates import get_timestamp_millis, iso_string_to_date

CASE_COUNT_UPPER_BOUND = 1000 * 1000 * 10
COUNTRY_COUNT_UPPER_BOUND = 1000 * 1000 * 10
DOMAIN_COUNT_UPPER_BOUND = 1000 * 1000 * 10
USER_COUNT_UPPER_BOUND = 1000 * 1000 * 10


def add_params_to_query(query, params):
    if params:
        for k in params:
            if k != 'search':
                query = query.filter({"terms": {k: params[k]}})
    return query


def get_data_point(count, date):
    return {
        "count": count,
        "time": get_timestamp_millis(date),
    }


def format_return_data(shown_data, initial_value, datespan):
    return {
        'histo_data': {
            "All Domains": add_blank_data(
                shown_data, datespan.startdate, datespan.enddate),
        },
        'initial_values': {"All Domains": initial_value},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


def add_blank_data(histo_data, start, end):
    if not histo_data:
        return [get_data_point(0, date) for date in [start, end]]
    return histo_data


def get_timestep(interval):
    if interval == 'day':
        return relativedelta(days=1)
    elif interval == 'week':
        return relativedelta(weeks=1)
    elif interval == 'month':
        return relativedelta(months=1)
    elif interval == 'year':
        return relativedelta(years=1)
    raise IntervalNotFoundException(unicode(interval))


def daterange(interval, start_date, end_date):
    """
    Generator that yields dates from start_date to end_date in the interval
    specified
    """
    cur_date = start_date
    step = get_timestep(interval)

    while cur_date <= end_date:
        yield cur_date
        cur_date += step


def intervals(interval, start_date, end_date):
    for starting_date in daterange(interval, start_date, end_date):
        closing_date = (
            starting_date + get_timestep(interval) - relativedelta(days=1)
        )
        ending_date = closing_date if closing_date < end_date else end_date
        yield (starting_date, ending_date)


def get_project_spaces(facets=None):
    """
    Returns a list of names of project spaces that satisfy the facets
    """
    real_domain_query = (
        DomainES()
        .fields(["name"])
        .size(DOMAIN_COUNT_UPPER_BOUND)
    )
    if facets:
        real_domain_query = add_params_to_query(real_domain_query, facets)
    domain_names = [hit['name'] for hit in real_domain_query.run().hits]
    if 'search' in facets:
        return list(set(domain_names) & set(facets['search']))
    return domain_names


def get_mobile_users(domains):
    return set(
        UserES()
        .show_inactive()
        .mobile_users()
        .domain(domains)
        .run().doc_ids
    )


def get_sms_query(begin, end, facet_name, facet_terms, domains):
    return (SMSES()
            .domain(domains)
            .received(gte=begin, lte=end)
            .terms_aggregation(facet_terms, facet_name)
            .size(0))


def get_active_countries_stats_data(domains, datespan, interval,
        datefield='received_on'):
    """
    Returns list of timestamps and how many countries were active in the 30
    days before the timestamp
    """
    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        t = timestamp
        f = timestamp - relativedelta(days=30)
        form_query = (FormES()
            .domain(domains)
            .terms_aggregation('domain', 'domains')
            .submitted(gte=f, lte=t)
            .size(0))

        domains = form_query.run().aggregations.domains.keys
        countries = (DomainES()
                .in_domains(domains)
                .terms_aggregation('countries', 'countries'))

        c = len(countries.run().aggregations.countries.keys)
        if c > 0:
            histo_data.append(get_data_point(c, timestamp))

    return format_return_data(histo_data, 0, datespan)


def domains_matching_plan(software_plan_edition, start, end):
    matching_subscriptions = Subscription.objects.filter(
        Q(date_start__lte=end) & Q(date_end__gte=start),
        plan_version__plan__edition=software_plan_edition,
    )

    return {
        subscription.subscriber.domain
        for subscription in matching_subscriptions
    }


def plans_on_date(software_plan_edition, date):
    matching_subscriptions = Subscription.objects.filter(
        Q(date_start__lte=date) & Q(date_end__gte=date),
        plan_version__plan__edition=software_plan_edition,
    )

    return {
        subscription.subscriber.domain
        for subscription in matching_subscriptions
    }


def get_subscription_stats_data(domains, datespan, interval,
        software_plan_edition=None):
    return [
        get_data_point(
            len(set(domains) & plans_on_date(
                software_plan_edition, timestamp)),
            timestamp
        )
        for timestamp in daterange(
            interval, datespan.startdate, datespan.enddate
        )
    ]


def get_active_domain_stats_data(domains, datespan, interval,
        datefield='received_on', software_plan_edition=None,
        add_form_domains=True, add_sms_domains=True,
        restrict_to_mobile_submissions=False):
    """
    Returns list of timestamps and how many domains were active in the 30 days
    before the timestamp
    """
    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        t = timestamp
        f = timestamp - relativedelta(days=30)
        domains_in_interval = (
            domains
            if software_plan_edition is None else
            list((set(domains) & domains_matching_plan(software_plan_edition, f, t)))
        )
        active_domains = set()
        if add_form_domains:
            form_query = (FormES()
                .domain(domains_in_interval)
                .terms_aggregation('domain', 'domains')
                .submitted(gte=f, lte=t)
                .size(0))
            if restrict_to_mobile_submissions:
                form_query = form_query.user_id(get_user_ids(True))
            active_domains |= set(
                form_query.run().aggregations.domains.keys
            )
        if add_sms_domains:
            sms_query = (get_sms_query(f, t, 'domains', 'domain', domains)
                .incoming_messages())
            active_domains |= set(
                sms_query.run().aggregations.domains.keys
            )
        c = len(active_domains)
        if c > 0:
            histo_data.append(get_data_point(c, timestamp))

    return format_return_data(histo_data, 0, datespan)


def get_active_users_data(domains, datespan, interval, datefield='date',
        additional_params_es={}, include_forms=False):
    """
    Returns list of timestamps and how many users of SMS were active in the
    30 days before each timestamp
    """
    histo_data = []
    mobile_users = get_mobile_users(domains)

    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        t = timestamp
        f = timestamp - relativedelta(days=30)
        sms_query = get_sms_query(f, t, 'users', 'couch_recipient', domains)
        if additional_params_es:
            sms_query = add_params_to_query(sms_query, additional_params_es)
        users = set(sms_query.incoming_messages().run().aggregations.users.keys)
        if include_forms:
            users |= set(
                FormES()
                .domain(domains)
                .user_aggregation()
                .submitted(gte=f, lte=t)
                .user_id(mobile_users)
                .size(0)
                .run()
                .aggregations.user.keys
            )
        c = len(users)
        if c > 0:
            histo_data.append(get_data_point(c, timestamp))

    return format_return_data(histo_data, 0, datespan)


def get_active_dimagi_owned_gateway_projects(domains, datespan, interval,
        datefield='date'):
    """
    Returns list of timestamps and how many domains used a Dimagi owned gateway
    in the past thrity days before each timestamp
    """
    dimagi_owned_backend_ids = SQLMobileBackend.get_global_backend_ids(
        SQLMobileBackend.SMS,
        couch_id=True
    )
    backend_filter = {'terms': {'backend_id': dimagi_owned_backend_ids}}

    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        t = timestamp
        f = timestamp - relativedelta(days=30)
        sms_query = get_sms_query(f, t, 'domains', 'domain', domains)
        d = sms_query.filter(backend_filter).run()
        c = len(d.aggregations.domains.keys)
        if c > 0:
            histo_data.append(get_data_point(c, timestamp))

    return format_return_data(histo_data, 0, datespan)


def get_countries_stats_data(domains, datespan, interval,
        datefield='created_on'):
    """
    Returns list of timestamps and how many countries have been created before
    each interval
    """
    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        countries = (DomainES()
                .in_domains(domains)
                .created(lte=timestamp)
                .terms_aggregation('countries', 'countries')
                .size(0))

        c = len(countries.run().aggregations.countries.keys)
        if c > 0:
            histo_data.append(get_data_point(c, timestamp))

    return format_return_data(histo_data, 0, datespan)


def get_active_supply_points_data(domains, datespan, interval):
    """
    Returns list of timestamps and active supply points have been modified during
    each interval
    """
    histo_data = []
    for start_date, end_date in intervals(interval, datespan.startdate, datespan.enddate):
        num_active_supply_points = (CaseES()
                .domain(domains)
                .case_type(SUPPLY_POINT_CASE_TYPE)
                .active_in_range(gte=start_date, lte=end_date)
                .size(0)).run().total

        if num_active_supply_points > 0:
            histo_data.append(get_data_point(num_active_supply_points, end_date))

    return format_return_data(histo_data, 0, datespan)


def get_total_clients_data(domains, datespan, interval, datefield='opened_on'):
    """
    Returns cases that have used SMS.
    Returned based on date case is opened
    """
    sms_cases = (SMSES()
            .to_commcare_case()
            .domain(domains)
            .terms_aggregation('couch_recipient', 'cases')
            .size(0))

    cases = sms_cases.run().aggregations.cases.keys

    cases_after_date = (CaseES()
            .domain(domains)
            .filter({"ids": {"values": cases}})
            .opened_range(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = cases_after_date.run().aggregations.date.as_facet_result()

    cases_before_date = (CaseES()
            .domain(domains)
            .filter({"ids": {"values": cases}})
            .opened_range(lt=datespan.startdate)
            .size(0)).run().total

    return format_return_data(histo_data, cases_before_date, datespan)


def get_mobile_workers_data(domains, datespan, interval,
        datefield='created_on'):
    """
    Returns mobile workers that have used SMS.
    Returned based on date mobile worker is created
    """
    sms_users = (SMSES()
            .to_commcare_user()
            .domain(domains)
            .terms_aggregation('couch_recipient', 'users')
            .size(0))

    users = sms_users.run().aggregations.users.keys

    users_after_date = (UserES()
            .domain(domains)
            .filter({"ids": {"values": users}})
            .mobile_users()
            .show_inactive()
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = users_after_date.run().aggregations.date.as_facet_result()

    users_before_date = (UserES()
            .domain(domains)
            .filter({"ids": {"values": users}})
            .mobile_users()
            .show_inactive()
            .created(lt=datespan.startdate)
            .size(0)).run().total

    return format_return_data(histo_data, users_before_date, datespan)


def get_real_sms_messages_data(domains, datespan, interval,
        datefield='date', is_commtrack=False, additional_params_es={}):
    """
    Returns SMS sent in timespan.
    Returned based on date SMS was sent
    """
    sms_after_date = (SMSES()
            .domain(domains)
            .received(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))
    if additional_params_es:
        sms_after_date = add_params_to_query(
            sms_after_date,
            additional_params_es
        )
    if is_commtrack:
        sms_after_date = sms_after_date.to_commcare_user_or_case()

    histo_data = sms_after_date.run().aggregations.date.as_facet_result()

    sms_before_date = (SMSES()
            .domain(domains)
            .received(lt=datespan.startdate)
            .size(0))

    if additional_params_es:
        sms_before_date = add_params_to_query(
            sms_before_date,
            additional_params_es
        )
    if is_commtrack:
        sms_before_date = sms_before_date.to_commcare_user_or_case()

    sms_before_date = sms_before_date.run().total

    return format_return_data(histo_data, sms_before_date, datespan)


def get_sms_only_domain_stats_data(domains, datespan, interval,
        datefield='date_created'):
    """
    Returns domains that have only used SMS and not forms.
    Returned based on date domain is created
    """
    histo_data = []

    sms = (SMSES()
            .domain(domains)
            .terms_aggregation('domain', 'domains')
            .size(0))
    forms = (FormES()
             .domain(domains)
             .terms_aggregation('domain', 'domains')
             .size(0))

    sms_domains = set(sms.run().aggregations.domains.keys)
    form_domains = set(forms.run().aggregations.domains.keys)

    sms_only_domains = sms_domains - form_domains

    domains_after_date = (DomainES()
            .in_domains(sms_only_domains)
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = domains_after_date.run().aggregations.date.as_facet_result()

    domains_before_date = (DomainES()
            .in_domains(sms_only_domains)
            .created(lt=datespan.startdate)
            .size(0))

    domains_before_date = domains_before_date.run().total
    return format_return_data(histo_data, domains_before_date, datespan)


def get_commconnect_domain_stats_data(domains, datespan, interval,
        datefield='date_created', additional_params_es={}):
    """
    Returns domains that have used SMS.
    Returned based on date domain is created
    """
    sms = (SMSES()
           .domain(domains)
           .terms_aggregation('domain', 'domains')
           .size(0))

    if additional_params_es:
        sms = add_params_to_query(sms, additional_params_es)

    sms_domains = set(sms.run().aggregations.domains.keys)

    domains_after_date = (DomainES()
            .in_domains(sms_domains)
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = domains_after_date.run().aggregations.date.as_facet_result()

    domains_before_date = (DomainES()
            .in_domains(sms_domains)
            .created(lt=datespan.startdate)
            .size(0))

    domains_before_date = domains_before_date.run().total
    return format_return_data(histo_data, domains_before_date, datespan)


def get_all_subscriptions_stats_data(domains, datespan, interval):
    return {
        'histo_data': {
            software_plan_edition_tuple[0]: add_blank_data(
                get_subscription_stats_data(
                    domains,
                    datespan,
                    interval,
                    software_plan_edition=software_plan_edition_tuple[0],
                ),
                datespan.startdate,
                datespan.enddate
            )
            for software_plan_edition_tuple in SoftwarePlanEdition.CHOICES
        },
        'initial_values': {
            software_plan_edition_tuple[0]: 0
            for software_plan_edition_tuple in SoftwarePlanEdition.CHOICES
        },
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


def get_domain_stats_data(domains, datespan, interval,
        datefield="date_created"):

    domains_after_date = (DomainES()
            .in_domains(domains)
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))
    histo_data = domains_after_date.run().aggregations.date.as_facet_result()

    domains_before_date = (DomainES()
            .in_domains(domains)
            .created(lt=datespan.startdate)
            .size(0))
    domains_before_date = domains_before_date.run().total

    return format_return_data(histo_data, domains_before_date, datespan)


def commtrack_form_submissions(domains, datespan, interval,
        datefield='received_on'):
    mobile_workers = UserES().exclude_source().mobile_users().show_inactive().run().doc_ids

    forms_after_date = (FormES()
            .domain(domains)
            .submitted(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .user_id(mobile_workers)
            .size(0))

    histo_data = forms_after_date.run().aggregations.date.as_facet_result()

    forms_before_date = (FormES()
            .domain(domains)
            .submitted(lt=datespan.startdate)
            .user_id(mobile_workers)
            .size(0))

    forms_before_date = forms_before_date.run().total

    return format_return_data(histo_data, forms_before_date, datespan)


def get_stock_transaction_stats_data(domains, datespan, interval):
    def get_stock_transactions_in_daterange(
            in_domains, end_date, start_date=None):
        def date_to_datetime(date):
            return datetime.datetime.fromordinal(date.toordinal())
        stock_report_query = StockReport.objects.filter(domain__in=in_domains)
        if start_date is not None:
            stock_report_query = stock_report_query.filter(
                date__gte=date_to_datetime(start_date)
            )
        stock_report_query = stock_report_query.filter(
            date__lt=(date_to_datetime(end_date) + relativedelta(days=1))
        )
        return StockTransaction.objects.filter(
            report__in=stock_report_query,
        ).count()

    return format_return_data(
        [
            get_data_point(
                get_stock_transactions_in_daterange(
                    domains,
                    enddate,
                    start_date=startdate,
                ),
                enddate
            )
            for startdate, enddate in intervals(
                interval,
                datespan.startdate,
                datespan.enddate,
            )
        ],
        get_stock_transactions_in_daterange(domains, datespan.enddate),
        datespan,
    )


def get_active_cases_stats(domains, datespan, interval, **kwargs):
    return get_other_stats("active_cases", domains, datespan, interval,
                           **kwargs)


def get_case_stats(domains, datespan, interval, **kwargs):
    return get_other_stats("cases", domains, datespan, interval, **kwargs)


def get_form_stats(domains, datespan, interval, **kwargs):
    return get_other_stats("forms", domains, datespan, interval, **kwargs)


def get_user_stats(domains, datespan, interval, **kwargs):
    return get_other_stats("users", domains, datespan, interval, **kwargs)


def get_users_all_stats(domains, datespan, interval,
                        user_type_mobile=None,
                        require_submissions=False):
    query = UserES().domain(domains).show_inactive().size(0)
    if user_type_mobile:
        query = query.mobile_users()
    elif user_type_mobile is not None:
        query = query.web_users()
    if require_submissions:
        query = query.user_ids(get_submitted_users())

    histo_data = (
        query
        .created(gte=datespan.startdate, lte=datespan.enddate)
        .date_histogram('date', 'created_on', interval)
        .run().aggregations.date.as_facet_result()
    )

    users_before_date = len(
        query
        .created(lt=datespan.startdate)
        .run().doc_ids
    )

    return format_return_data(histo_data, users_before_date, datespan)


def get_other_stats(histo_type, domains, datespan, interval,
        individual_domain_limit=16, is_cumulative="True",
        user_type_mobile=None, supply_points=False, j2me_only=False):
    """
    A catch all for graphs that are not complex.

    individual_domain_limit: after limit make graph apply to all domains instead
                             graphing each individually
    user_type_mobile: mobile or web users
    supply_points: used for cases that are supply points
    """
    if len(domains) <= individual_domain_limit:
        domain_info = [{"names": [d], "display_name": d} for d in domains]
    elif len(domains) < ES_MAX_CLAUSE_COUNT:
        domain_info = [{"names": [d for d in domains],
                        "display_name": _("Domains Matching Filter")}]
    else:
        domain_info = [{
            "names": None,
            "display_name": _(
                "All Domains (NOT applying filters. > %s projects)"
                % ES_MAX_CLAUSE_COUNT
            )
        }]

    stats_data = get_general_stats_data(
        domain_info,
        histo_type,
        datespan,
        interval=interval,
        user_type_mobile=user_type_mobile,
        is_cumulative=is_cumulative == "True",
        supply_points=supply_points,
        j2me_only=j2me_only
    )
    if not stats_data['histo_data']:
        stats_data['histo_data'][''] = []
        stats_data['initial_values'] = {'': 0}
    for k in stats_data['histo_data']:
        stats_data['histo_data'][k] = add_blank_data(
            stats_data["histo_data"][k],
            datespan.startdate,
            datespan.enddate
        )
    return stats_data


def get_products_stats_data(domains, datespan, interval,
        datefield='created_at'):
    """
    Number of products by created time
    """
    # groups products by the interval and returns the time interval and count
    ret = (SQLProduct.objects
                     .filter(domain__in=domains,
                             created_at__gte=datespan.startdate,
                             created_at__lte=datespan.enddate)
                     .extra({
                         interval:
                             "EXTRACT(EPOCH FROM date_trunc('%s', %s))*1000" %
                             (interval, datefield)})
                     .values(interval).annotate(Count('id')))

    ret = [{"time": int(r[interval]), "count": r['id__count']} for r in ret]

    initial = (SQLProduct.objects
                     .filter(domain__in=domains,
                             created_at__lt=datespan.startdate)
                     .count())

    return format_return_data(ret, initial, datespan)


def get_user_ids(user_type_mobile):
    """
    Returns the set of mobile user IDs if user_type_mobile is True,
    else returns the set of web user IDs.
    """
    query = UserES().show_inactive()
    if user_type_mobile:
        query = query.mobile_users()
    else:
        query = query.web_users()
    return set(query.run().doc_ids)


def get_submitted_users():
    real_form_users = set(
        FormES()
        .user_aggregation()
        .size(0)
        .run()
        .aggregations.user.keys
    )

    real_sms_users = set(
        SMSES()
        .terms_aggregation('couch_recipient', 'user')
        .incoming_messages()
        .size(0)
        .run()
        .aggregations.user.keys
    )

    return real_form_users | real_sms_users


def get_case_owner_filters():
    result = {'terms': {}}

    mobile_user_ids = list(get_user_ids(True))

    def all_groups():
        for domain in Domain.get_all():
            for group in Group.by_domain(domain.name):
                yield group
    group_ids = [
        group._id for group in all_groups()
    ]

    result['terms']['owner_id'] = mobile_user_ids + group_ids
    return result


def _histo_data(domain_list, histogram_type, start_date, end_date, interval,
        filters):
    return dict([
        (
            d['display_name'],
            es_histogram(
                histogram_type,
                d["names"],
                start_date,
                end_date,
                interval=interval,
                filters=filters,
            )
        ) for d in domain_list
    ])


def _histo_data_non_cumulative(domain_list, histogram_type, start_date,
        end_date, interval, filters):
    def _get_active_length(histo_type):
        # TODO - add to configs
        return 90 if histogram_type == 'active_cases' else 30

    timestamps = daterange(interval, iso_string_to_date(start_date),
                           iso_string_to_date(end_date))
    histo_data = {}
    for domain_name_data in domain_list:
        display_name = domain_name_data['display_name']
        domain_data = []
        for timestamp in timestamps:
            past_30_days = _histo_data(
                [domain_name_data],
                histogram_type,
                (timestamp - relativedelta(
                        days=_get_active_length())).isoformat(),
                timestamp.isoformat(),
                filters
            )
            domain_data.append(
                get_data_point(
                    sum(point['count']
                        for point in past_30_days[display_name]),
                    timestamp
                )
            )
        histo_data.update({
            display_name: domain_data
        })
    return histo_data


def _total_until_date(histogram_type, datespan, filters=[], domain_list=None):
    """
    Returns the initial values for the non cumulative graphs
    """
    query = {
        "in": {"domain.exact": domain_list}
    } if domain_list is not None else {"match_all": {}}
    q = {
        "query": query,
        "filter": {
            "and": [
                {
                    "range": {
                        DATE_FIELDS[histogram_type]: {
                            "lt": datespan.startdate_display
                        }
                    }
                },
            ],
        },
    }
    q["filter"]["and"].extend(ADD_TO_ES_FILTER.get(histogram_type, [])[:])
    q["filter"]["and"].extend(filters)

    return es_query(
        q=q,
        es_index=histogram_type,
        size=0,
    )["hits"]["total"]


def get_general_stats_data(domains, histo_type, datespan, interval="day",
        user_type_mobile=None, is_cumulative=True, supply_points=False,
        j2me_only=False):
    additional_filters = []
    if histo_type == 'forms':
        if user_type_mobile is not None:
            additional_filters.append({
                'terms': {
                    'form.meta.userID': list(get_user_ids(user_type_mobile))
                }
            })
        if j2me_only:
            additional_filters.append({
                'regexp': {
                    'form.meta.appVersion': "v2+.[0-9]+.*"
                }
            })
    if histo_type == 'active_cases' and not supply_points:
        additional_filters.append(get_case_owner_filters())
    if supply_points:
        additional_filters.append({'terms': {'type': ['supply-point']}})

    hist_data_func = (
        _histo_data if is_cumulative else _histo_data_non_cumulative
    )
    histo_data = hist_data_func(
        domains,
        histo_type,
        datespan.startdate_display,
        datespan.enddate_display,
        interval,
        additional_filters
    )

    return {
        'histo_data': histo_data,
        'initial_values': {
            domain_data["display_name"]: _total_until_date(
                histo_type,
                datespan,
                filters=additional_filters,
                domain_list=domain_data["names"],
            ) for domain_data in domains
        } if is_cumulative else {"All Domains": 0},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


def _sql_to_json_data(domains, sql_data, datespan, individual_domain_limit=16):
    """
    Helper function to transform sql queries into what the admin reports
    framework likes. Handles initial values and historical data

    sql_data needs {'timestamp': t, 'domain': d}
    """
    all_domains = len(domains) > individual_domain_limit
    start = get_timestamp_millis(datespan.startdate)

    if all_domains:
        histo_data = {"All Domains": dict()}
        init_ret = {"All Domains": 0}
        ret = {"All Domains": list()}
    else:
        histo_data = {d: dict() for d in domains}
        init_ret = {d: 0 for d in domains}
        ret = {d: list() for d in domains}

    for data in sql_data:
        tstamp = get_timestamp_millis(data['timestamp'])
        domain = "All Domains" if all_domains else data['domain']

        if tstamp < start:
            init_ret[domain] += 1
        else:
            if tstamp not in histo_data[domain]:
                histo_data[domain][tstamp] = 1
            else:
                histo_data[domain][tstamp] += 1

    for k, v in histo_data.iteritems():
        for l, w in v.iteritems():
            ret[k].append({'count': w, 'time': l})

    return init_ret, ret


def get_unique_locations_data(domains, datespan, interval,
        datefield='created_at', individual_domain_limit=16):
    locations = (SQLLocation.objects
                            .filter(domain__in=domains,
                                    created_at__lte=datespan.enddate)
                            .extra({"timestamp":
                                    "date_trunc('%s', %s)" %
                                    (interval, datefield)})
                            .values("timestamp", "domain"))

    domains = {l["domain"] for l in locations}

    init_ret, ret = _sql_to_json_data(domains, locations, datespan,
            individual_domain_limit=individual_domain_limit)

    return {
        'histo_data': ret,
        'initial_values': init_ret,
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


def get_location_type_data(domains, datespan, interval,
        datefield='created_at', individual_domain_limit=16):
    locations = (SQLLocation.objects
                            .filter(domain__in=domains,
                                    created_at__lte=datespan.enddate)
                            .extra({"timestamp":
                                    "date_trunc('%s', %s)" %
                                    (interval, datefield)})
                            .values("timestamp", "domain", "location_type")
                            .order_by("location_type", "created_at")
                            .distinct("location_type"))

    domains = {l["domain"] for l in locations}

    init_ret, ret = _sql_to_json_data(domains, locations, datespan,
            individual_domain_limit=individual_domain_limit)

    return {
        'histo_data': ret,
        'initial_values': init_ret,
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


HISTO_TYPE_TO_FUNC = {
    "active_cases": get_active_cases_stats,
    "active_countries": get_active_countries_stats_data,
    "active_dimagi_gateways": get_active_dimagi_owned_gateway_projects,
    "active_domains": get_active_domain_stats_data,
    "active_mobile_users": get_active_users_data,
    "active_supply_points": get_active_supply_points_data,
    "cases": get_case_stats,
    "commtrack_forms": commtrack_form_submissions,
    "countries": get_countries_stats_data,
    "domains": get_domain_stats_data,
    "forms": get_form_stats,
    "location_types": get_location_type_data,
    "mobile_clients": get_total_clients_data,
    "mobile_workers": get_mobile_workers_data,
    "real_sms_messages": get_real_sms_messages_data,
    "sms_domains": get_commconnect_domain_stats_data,
    "sms_only_domains": get_sms_only_domain_stats_data,
    "stock_transactions": get_stock_transaction_stats_data,
    "subscriptions": get_all_subscriptions_stats_data,
    "total_products": get_products_stats_data,
    "unique_locations": get_unique_locations_data,
    "users": get_user_stats,
    "users_all": get_users_all_stats,
}


def get_stats_data(histo_type, domain_params, datespan, interval, **kwargs):
    if histo_type in HISTO_TYPE_TO_FUNC:
        return HISTO_TYPE_TO_FUNC[histo_type](
            domain_params,
            datespan,
            interval,
            **kwargs
        )
    raise HistoTypeNotFoundException(histo_type)
