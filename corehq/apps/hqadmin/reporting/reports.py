import datetime
import time
from dateutil.relativedelta import relativedelta
from django.db.models import Q
from django.utils.translation import ugettext as _

from corehq.apps.accounting.models import Subscription, SoftwarePlanEdition
from corehq.apps.es.cases import CaseES
from corehq.apps.es.domains import DomainES
from corehq.apps.es.forms import FormES
from corehq.apps.es.sms import SMSES
from corehq.apps.es.users import UserES
from corehq.apps.hqadmin.reporting.exceptions import IntervalNotFoundException
from corehq.apps.sms.mixin import SMSBackend
from corehq.elastic import (
    ES_MAX_CLAUSE_COUNT,
    get_general_stats_data,
    get_user_ids,
)

from casexml.apps.stock.models import StockReport, StockTransaction

LARGE_ES_NUMBER = 10 ** 6


class HistoTypeNotFound(Exception):
    pass


def add_params_to_query(query, params):
    if params:
        for k in params:
            query = query.filter({"terms": {k: params[k]}})
    return query


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
        return [
            {
                "count": 0,
                "time": timestamp,
            } for timestamp in [
                int(1000 * time.mktime(date.timetuple()))
                for date in [start, end]
            ]
        ]
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


def get_real_project_spaces(facets=None):
    """
    Returns a set of names of real domains
    """
    real_domain_query = DomainES().fields(['name'])
    if facets:
        real_domain_query = add_params_to_query(real_domain_query, facets)
    real_domain_query_results = real_domain_query.run().raw_hits
    return {x['fields']['name'] for x in real_domain_query_results}


def get_sms_query(begin, end, facet_name, facet_terms, domains,
        size=LARGE_ES_NUMBER):
    """
    Returns query in domains from the begin to end
    """
    return (SMSES()
            .in_domains(domains)
            .received(gte=begin, lte=end)
            .terms_facet(facet_name, facet_terms, size)
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
            .in_domains(domains)
            .submitted(gte=f, lte=t)
            .terms_facet('domains', 'domain', size=LARGE_ES_NUMBER)
            .size(0))

        domains = form_query.run().facet('domains', "terms")
        domains = [x['term'] for x in domains]
        countries = (DomainES()
                .in_domains(domains)
                .terms_facet('countries', 'country', size=LARGE_ES_NUMBER))

        c = len(countries.run().facet('countries', 'terms'))
        if c > 0:
            histo_data.append({"count": c, "time": 1000 *
                time.mktime(timestamp.timetuple())})

    return format_return_data(histo_data, 0, datespan)


def domains_matching_plan(software_plan_edition, start, end):
    matching_subscriptions = Subscription.objects.filter(
        ((Q(date_start__gte=start) & Q(date_start__lte=end))
            | (Q(date_end__gte=start) & Q(date_end__lte=end))),
        plan_version__plan__edition=software_plan_edition,
    )

    return {
        subscription.subscriber.domain
        for subscription in matching_subscriptions
    }


def get_subscription_stats_data(domains, datespan, interval,
        software_plan_edition=None):
    return [
        {
            "count": len(domains & domains_matching_plan(
                software_plan_edition, timestamp, timestamp)),
            "time": int(1000 * time.mktime(timestamp.timetuple())),
        } for timestamp in daterange(
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
            (domains & domains_matching_plan(software_plan_edition, f, t))
        )
        active_domains = set()
        if add_form_domains:
            form_query = (FormES()
                .in_domains(domains_in_interval)
                .submitted(gte=f, lte=t)
                .terms_facet('domains', 'domain', size=LARGE_ES_NUMBER)
                .size(0))
            if restrict_to_mobile_submissions:
                form_query = form_query.user_id(get_user_ids(True))
            active_domains |= {
                term_and_count['term'] for term_and_count in
                form_query.run().facet('domains', "terms")
            }
        if add_sms_domains:
            sms_query = (get_sms_query(f, t, 'domains', 'domain', domains)
                .incoming_messages())
            active_domains |= {
                term_and_count['term'] for term_and_count in
                sms_query.run().facet('domains', "terms")
            }
        c = len(active_domains)
        if c > 0:
            histo_data.append({"count": c, "time": 1000 *
                time.mktime(timestamp.timetuple())})

    return format_return_data(histo_data, 0, datespan)


def get_active_mobile_users_data(domains, datespan, interval, datefield='date',
        additional_params_es={}):
    """
    Returns list of timestamps and how many users of SMS were active in the
    30 days before the timestamp
    """
    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        t = timestamp
        f = timestamp - relativedelta(days=30)
        sms_query = get_sms_query(f, t, 'users', 'couch_recipient',
                domains)
        if additional_params_es:
            sms_query = add_params_to_query(sms_query, additional_params_es)
        users = sms_query.run().facet('users', "terms")
        c = len(users)
        if c > 0:
            histo_data.append({"count": c, "time":
                1000 * time.mktime(timestamp.timetuple())})

    return format_return_data(histo_data, 0, datespan)


def get_active_dimagi_owned_gateway_projects(domains, datespan, interval,
        datefield='date'):
    """
    Returns list of timestamps and how many domains used a Dimagi owned gateway
    in the past thrity days before each timestamp
    """
    dimagi_owned_backend = SMSBackend.view(
        "sms/global_backends",
        reduce=False
    ).all()

    dimagi_owned_backend_ids = [x['id'] for x in dimagi_owned_backend]
    backend_filter = {'terms': {'backend_id': dimagi_owned_backend_ids}}

    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        t = timestamp
        f = timestamp - relativedelta(days=30)
        sms_query = get_sms_query(f, t, 'domains', 'domain', domains)
        d = sms_query.filter(backend_filter).run()
        c = len(d.facet('domains', 'terms'))
        if c > 0:
            histo_data.append({"count": c, "time": 1000 *
                time.mktime(timestamp.timetuple())})

    return format_return_data(histo_data, 0, datespan)


def get_countries_stats_data(domains, datespan, interval,
        datefield='created_on'):
    """
    Returns list of timestamps and how many countries have been created
    """
    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        countries = (DomainES()
                .in_domains(domains)
                .created(lte=timestamp)
                .terms_facet('countries', 'country', size=LARGE_ES_NUMBER)
                .size(0))

        c = len(countries.run().facet('countries', 'terms'))
        if c > 0:
            histo_data.append({"count": c, "time": 1000 *
                time.mktime(timestamp.timetuple())})

    return format_return_data(histo_data, 0, datespan)


def get_total_clients_data(domains, datespan, interval, datefield='opened_on'):
    """
    Returns cases that have used SMS.
    Returned based on date case is opened
    """
    sms_cases = (SMSES()
            .to_commcare_case()
            .in_domains(domains)
            .terms_facet('cases', 'couch_recipient', size=LARGE_ES_NUMBER)
            .size(0))

    cases = [u['term'] for u in sms_cases.run().facet('cases', 'terms')]

    cases_after_date = (CaseES()
            .in_domains(domains)
            .filter({"ids": {"values": cases}})
            .opened_range(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = cases_after_date.run().facet('date', 'entries')

    cases_before_date = (CaseES()
            .in_domains(domains)
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
            .in_domains(domains)
            .terms_facet('users', 'couch_recipient', LARGE_ES_NUMBER)
            .size(0))

    users = [u['term'] for u in sms_users.run().facet('users', 'terms')]

    users_after_date = (UserES()
            .in_domains(domains)
            .filter({"ids": {"values": users}})
            .mobile_users()
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = users_after_date.run().facet('date', 'entries')

    users_before_date = (UserES()
            .in_domains(domains)
            .filter({"ids": {"values": users}})
            .mobile_users()
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
            .in_domains(domains)
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

    histo_data = sms_after_date.run().facet('date', 'entries')

    sms_before_date = (SMSES()
            .in_domains(domains)
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
            .in_domains(domains)
            .terms_facet('domains', 'domain', size=LARGE_ES_NUMBER)
            .size(0))
    forms = (FormES()
             .in_domains(domains)
             .terms_facet('domains', 'domain', size=LARGE_ES_NUMBER)
             .size(0))

    sms_domains = {x['term'] for x in sms.run().facet('domains', 'terms')}
    form_domains = {x['term'] for x in forms.run().facet('domains', 'terms')}

    sms_only_domains = sms_domains - form_domains

    domains_after_date = (DomainES()
            .in_domains(sms_only_domains)
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = domains_after_date.run().facet('date', 'entries')

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
           .in_domains(domains)
           .terms_facet('domains', 'domain', size=LARGE_ES_NUMBER)
           .size(0))

    if additional_params_es:
        sms = add_params_to_query(sms, additional_params_es)

    sms_domains = {x['term'] for x in sms.run().facet('domains', 'terms')}

    domains_after_date = (DomainES()
            .in_domains(sms_domains)
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = domains_after_date.run().facet('date', 'entries')

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
    histo_data = domains_after_date.run().facet('date', 'entries')

    domains_before_date = (DomainES()
            .in_domains(domains)
            .created(lt=datespan.startdate)
            .size(0))
    domains_before_date = domains_before_date.run().total

    return format_return_data(histo_data, domains_before_date, datespan)


def commtrack_form_submissions(domains, datespan, interval,
        datefield='received_on'):
    mobile_workers = [a['_id'] for a in
            UserES().fields([]).mobile_users().run().raw_hits]

    forms_after_date = (FormES()
            .in_domains(domains)
            .submitted(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .user_id(mobile_workers)
            .size(0))

    histo_data = forms_after_date.run().facet('date', 'entries')

    forms_before_date = (FormES()
            .in_domains(domains)
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
        return sum(
            StockTransaction.objects.filter(report=stock_report)
            for stock_report in stock_report_query
        )

    return format_return_data(
        [
            {
                "count": get_stock_transactions_in_daterange(
                    domains,
                    enddate,
                    start_date=startdate,
                ),
                "time": 1000 * time.mktime(enddate.timetuple()),
            }
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


def get_other_stats(histo_type, domains, datespan, interval,
        individual_domain_limit=16, is_cumulative="True",
        user_type_mobile=None, require_submissions=True, supply_points=False):
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
        require_submissions=require_submissions,
        supply_points=supply_points,
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


HISTO_TYPE_TO_FUNC = {
    "active_cases": get_active_cases_stats,
    "active_countries": get_active_countries_stats_data,
    "active_dimagi_gateways": get_active_dimagi_owned_gateway_projects,
    "active_domains": get_active_domain_stats_data,
    "active_mobile_users": get_active_mobile_users_data,
    "cases": get_case_stats,
    "commtrack_forms": commtrack_form_submissions,
    "countries": get_countries_stats_data,
    "domains": get_domain_stats_data,
    "forms": get_form_stats,
    "mobile_clients": get_total_clients_data,
    "mobile_workers": get_mobile_workers_data,
    "real_sms_messages": get_real_sms_messages_data,
    "sms_domains": get_commconnect_domain_stats_data,
    "sms_only_domains": get_sms_only_domain_stats_data,
    "stock_transactions": get_stock_transaction_stats_data,
    "subscriptions": get_all_subscriptions_stats_data,
    "users": get_user_stats,
}


def get_stats_data(histo_type, domain_params, datespan, interval, **kwargs):
    if histo_type in HISTO_TYPE_TO_FUNC:
        return HISTO_TYPE_TO_FUNC[histo_type](
            domain_params,
            datespan,
            interval,
            **kwargs
        )
    raise HistoTypeNotFound(histo_type)
