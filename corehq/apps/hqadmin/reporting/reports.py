import time
from copy import deepcopy
from dateutil.relativedelta import relativedelta
from django.db.models import Q

from corehq.apps.accounting.models import Subscription
from corehq.apps.es.cases import CaseES
from corehq.apps.es.domains import DomainES
from corehq.apps.es.forms import FormES
from corehq.apps.es.sms import SMSES
from corehq.apps.es.users import UserES
from corehq.apps.sms.mixin import SMSBackend
from corehq.elastic import es_query, ES_URLS


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


def daterange(interval, start_date, end_date):
    """
    Generator that yields dates from start_date to end_date in the interval
    specified
    """
    cur_date = start_date
    if interval == 'day':
        step = relativedelta(days=1)
    elif interval == 'week':
        step = relativedelta(weeks=1)
    elif interval == 'month':
        step = relativedelta(months=1)
    elif interval == 'year':
        step = relativedelta(years=1)

    while cur_date < end_date:
        yield cur_date
        cur_date += step


def get_real_project_spaces(is_commtrack=False, is_commcommconnect=False):
    """
    Returns a set of names of real domains
    """
    real_domain_query = DomainES().real_domains().fields(['name'])
    if is_commtrack:
        real_domain_query = real_domain_query.commtrack_domains()
    if is_commcommconnect:
        real_domain_query = real_domain_query.commconnect_domains()
    real_domain_query_results = real_domain_query.run().raw_hits
    return {x['fields']['name'] for x in real_domain_query_results}


def get_sms_query(begin, end, facet_name, facet_terms, domains):
    """
    Returns query in domains from the begin to end
    """
    return (SMSES()
            .in_domains(domains)
            .received(gte=begin, lte=end)
            .terms_facet(facet_name, facet_terms, size=10000)
            .size(0))


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


def get_subscription_stats_data(params, datespan, interval='month',
        software_plan_edition=None):
    real_domains = get_real_project_spaces()
    return [
        {
            "count": len(real_domains & domains_matching_plan(
                software_plan_edition, timestamp, timestamp)),
            "time": int(1000 * time.mktime(timestamp.timetuple())),
        } for timestamp in daterange(
            interval, datespan.startdate, datespan.enddate
        )
    ]


def get_active_domain_stats_data(params, datespan, interval='month',
        datefield='received_on', software_plan_edition=None):
    """
    Returns list of timestamps and how many domains were active in the 30 days
    before the timestamp
    """
    real_domains = get_real_project_spaces()

    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        t = timestamp
        f = timestamp - relativedelta(days=30)
        form_query = (FormES()
            .in_domains(
                real_domains if software_plan_edition is None else (
                    real_domains & domains_matching_plan(
                        software_plan_edition, f, t)
                )
            )
            .submitted(gte=f, lte=t)
            .terms_facet('domains', 'domain')
            .size(0))

        domains = form_query.run().facet('domains', "terms")
        c = len(domains)
        if c > 0:
            histo_data.append({"count": c, "time": 1000 *
                time.mktime(timestamp.timetuple())})

    return format_return_data(histo_data, 0, datespan)


def get_active_mobile_users_data(params, datespan, interval='month',
        datefield='date'):
    """
    Returns list of timestamps and how many users of SMS were active in the
    30 days before the timestamp
    """

    real_domains = get_real_project_spaces()

    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        t = timestamp
        f = timestamp - relativedelta(days=30)
        sms_query = get_sms_query(f, t, 'users', 'couch_recipient',
                real_domains).filter({"terms": params})
        users = sms_query.run().facet('users', "terms")
        c = len(users)
        if c > 0:
            histo_data.append({"count": c, "time":
                1000 * time.mktime(timestamp.timetuple())})

    return format_return_data(histo_data, 0, datespan)


def get_active_commconnect_domain_stats_data(params, datespan,
        interval='month', datefield='date'):
    """
    Returns list of timestamps and how many commconnect domains were active in
    the 30 days before the timestamp
    """
    real_domains = get_real_project_spaces()

    histo_data = []
    for timestamp in daterange(interval, datespan.startdate, datespan.enddate):
        t = timestamp
        f = timestamp - relativedelta(days=30)
        sms_query = get_sms_query(f, t, 'domains', 'domain', real_domains)
        domains = sms_query.run()
        c = len(domains.facet('domains', 'terms'))
        if c > 0:
            histo_data.append({"count": c, "time": 1000 *
                time.mktime(timestamp.timetuple())})

    return format_return_data(histo_data, 0, datespan)


def get_active_dimagi_owned_gateway_projects(params, datespan,
        interval='month', datefield='date'):
    """
    Returns list of timestamps and how many domains used a Dimagi owned gateway
    in the past thrity days before each timestamp
    """
    real_domains = get_real_project_spaces()

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
        sms_query = get_sms_query(f, t, 'domains', 'domain', real_domains)
        domains = sms_query.filter(backend_filter).run()
        c = len(domains.facet('domains', 'terms'))
        if c > 0:
            histo_data.append({"count": c, "time": 1000 *
                time.mktime(timestamp.timetuple())})

    return format_return_data(histo_data, 0, datespan)


def get_total_clients_data(params, datespan, interval='month',
        datefield='opened_on'):
    """
    Returns cases that have used SMS.
    Returned based on date case is opened
    """
    real_domains = get_real_project_spaces()

    sms_cases = (SMSES()
            .to_commcare_case()
            .in_domains(real_domains)
            .terms_facet('cases', 'couch_recipient', size=100000)
            .size(0))

    cases = [u['term'] for u in sms_cases.run().facet('cases', 'terms')]

    cases_after_date = (CaseES()
            .in_domains(real_domains)
            .filter({"ids": {"values": cases}})
            .opened_range(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = cases_after_date.run().facet('date', 'entries')

    cases_before_date = (CaseES()
            .in_domains(real_domains)
            .filter({"ids": {"values": cases}})
            .opened_range(lt=datespan.startdate)
            .size(0)).run().total

    return format_return_data(histo_data, cases_before_date, datespan)


def get_mobile_workers_data(params, datespan, interval='month',
        datefield='created_on'):
    """
    Returns mobile workers that have used SMS.
    Returned based on date mobile worker is created
    """
    real_domains = get_real_project_spaces()

    sms_users = (SMSES()
            .to_commcare_user()
            .in_domains(real_domains)
            .terms_facet('users', 'couch_recipient', 100000)
            .size(0))

    users = [u['term'] for u in sms_users.run().facet('users', 'terms')]

    users_after_date = (UserES()
            .in_domains(real_domains)
            .filter({"ids": {"values": users}})
            .mobile_users()
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = users_after_date.run().facet('date', 'entries')

    users_before_date = (UserES()
            .in_domains(real_domains)
            .filter({"ids": {"values": users}})
            .mobile_users()
            .created(lt=datespan.startdate)
            .size(0)).run().total

    return format_return_data(histo_data, users_before_date, datespan)


def get_real_sms_messages_data(params, datespan, interval='month',
        datefield='date', is_commtrack=False):
    """
    Returns SMS sent in timespan.
    Returned based on date SMS was sent
    """
    real_domains = get_real_project_spaces(is_commtrack=is_commtrack)

    sms_after_date = (SMSES()
            .filter({"terms": params})
            .in_domains(real_domains)
            .received(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    if is_commtrack:
        sms_after_date = sms_after_date.to_commcare_user_or_case()

    histo_data = sms_after_date.run().facet('date', 'entries')

    sms_before_date = (SMSES()
            .in_domains(real_domains)
            .received(lt=datespan.startdate)
            .size(0))

    if is_commtrack:
        sms_before_date = sms_before_date.to_commcare_user_or_case()

    sms_before_date = sms_before_date.run().total

    return format_return_data(histo_data, sms_before_date, datespan)


def get_sms_only_domain_stats_data(datespan, interval='month',
        datefield='date_created'):
    """
    Returns domains that have only used SMS and not forms.
    Returned based on date domain is created
    """
    histo_data = []

    sms = (SMSES()
            .terms_facet('domains', 'domain')
            .size(0))
    forms = (FormES()
             .terms_facet('domains', 'domain')
             .size(0))

    sms_domains = {x['term'] for x in sms.run().facet('domains', 'terms')}
    form_domains = {x['term'] for x in forms.run().facet('domains', 'terms')}

    sms_only_domains = sms_domains - form_domains

    domains_after_date = (DomainES()
            .real_domains()
            .filter({"terms": {"name": list(sms_only_domains)}})
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = domains_after_date.run().facet('date', 'entries')

    domains_before_date = (DomainES()
            .real_domains()
            .filter({"terms": {"name": list(sms_only_domains)}})
            .created(lt=datespan.startdate)
            .size(0)).run().total

    return format_return_data(histo_data, domains_before_date, datespan)


def get_commconnect_domain_stats_data(params, datespan, interval='month',
        datefield='date_created'):
    """
    Returns domains that have used SMS.
    Returned based on date domain is created
    """
    sms = (SMSES()
           .terms_facet('domains', 'domain')
           .size(0))

    if len(params.keys()) > 0:
        sms = sms.filter({"terms": params})

    sms_domains = {x['term'] for x in sms.run().facet('domains', 'terms')}

    domains_after_date = (DomainES()
            .filter({"terms": {"name": list(sms_domains)}})
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = domains_after_date.run().facet('date', 'entries')

    domains_before_date = (DomainES()
            .real_domains()
            .filter({"terms": {"name": list(sms_domains)}})
            .created(lt=datespan.startdate)
            .size(0)).run().total

    return format_return_data(histo_data, domains_before_date, datespan)


def get_domain_stats_data(params, datespan, interval='week',
        datefield="date_created"):

    domains_after_date = (DomainES()
            .created(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = domains_after_date.run().facet('date', 'entries')

    domains_before_date = (DomainES()
            .real_domains()
            .created(lt=datespan.startdate)
            .size(0)).run().total

    return format_return_data(histo_data, domains_before_date, datespan)


def commtrack_form_submissions(params, datespan, interval='week',
        datefield='received_on'):
    real_domains = get_real_project_spaces(is_commtrack=True)
    mobile_workers = [a['_id'] for a in UserES().fields([]).mobile_users().run().raw_hits]

    forms_after_date = (FormES()
            .in_domains(real_domains)
            .submitted(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .user_id(mobile_workers)
            .size(0))

    histo_data = forms_after_date.run().facet('date', 'entries')

    forms_before_date = (FormES()
            .in_domains(real_domains)
            .submitted(lt=datespan.startdate)
            .user_id(mobile_workers)
            .size(0))

    forms_before_date = forms_before_date.run().total

    return format_return_data(histo_data, forms_before_date, datespan)
