import time
from copy import deepcopy
from dateutil.relativedelta import relativedelta

from corehq.apps.es.cases import CaseES
from corehq.apps.es.domains import DomainES
from corehq.apps.es.forms import FormES
from corehq.apps.es.sms import SMSES
from corehq.apps.es.users import UserES
from corehq.apps.sms.mixin import SMSBackend
from corehq.elastic import es_query, ES_URLS


def add_blank_data(stat_data, start, end):
    histo_data = stat_data.get("histo_data", {}).get("All Domains", [])
    if not histo_data:
        new_stat_data = deepcopy(stat_data)
        new_stat_data["histo_data"]["All Domains"] = [
            {
                "count": 0,
                "time": timestamp,
            } for timestamp in [
                int(1000 * time.mktime(date.timetuple()))
                for date in [start, end]
            ]
        ]
        return new_stat_data
    return stat_data


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


def get_real_project_spaces():
    """
    Returns a set of names of real domains
    """
    real_domain_query = DomainES().real_domains().fields(['name'])
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


def get_active_domain_stats_data(params, datespan, interval='month',
        datefield='received_on'):
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
            .in_domains(real_domains)
            .submitted(gte=f, lte=t)
            .terms_facet('domains', 'domain')
            .size(0))

        domains = form_query.run().facet('domains', "terms")
        c = len(domains)
        if c > 0:
            histo_data.append({"count": c, "time": 1000 *
                time.mktime(timestamp.timetuple())})

    return {
        'histo_data': {"All Domains": histo_data},
        'initial_values': {"All Domains": 0},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


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

    return {
        'histo_data': {"All Domains": histo_data},
        'initial_values': {"All Domains": 0},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


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

    return {
        'histo_data': {"All Domains": histo_data},
        'initial_values': {"All Domains": 0},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


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

    return {
        'histo_data': {"All Domains": histo_data},
        'initial_values': {"All Domains": 0},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


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

    return {
        'histo_data': {"All Domains": histo_data},
        'initial_values': {"All Domains": cases_before_date},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


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

    return {
        'histo_data': {"All Domains": histo_data},
        'initial_values': {"All Domains": users_before_date},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


def get_real_sms_messages_data(params, datespan, interval='month',
        datefield='date'):
    """
    Returns SMS sent in timespan.
    Returned based on date SMS was sent
    """
    real_domains = get_real_project_spaces()
    sms_after_date = (SMSES()
            .filter({"terms": params})
            .in_domains(real_domains)
            .received(gte=datespan.startdate, lte=datespan.enddate)
            .date_histogram('date', datefield, interval)
            .size(0))

    histo_data = sms_after_date.run().facet('date', 'entries')

    sms_before_date = (SMSES()
            .in_domains(real_domains)
            .received(lt=datespan.startdate)
            .size(0)).run().total

    return {
        'histo_data': {"All Domains": histo_data},
        'initial_values': {"All Domains": sms_before_date},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


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
            .size(0)).run()

    return {
        'histo_data': {"All Domains": histo_data},
        'initial_values': {"All Domains": domains_before_date.total},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


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
            .size(0)).run()

    return {
        'histo_data': {"All Domains": histo_data},
        'initial_values': {"All Domains": domains_before_date.total},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }


def get_domain_stats_data(params, datespan, interval='week',
        datefield="date_created"):
    q = {
        "query": {"bool": {"must":
                                  [{"match": {'doc_type': "Domain"}},
                                   {"term": {"is_snapshot": False}}]}},
        "facets": {
            "histo": {
                "date_histogram": {
                    "field": datefield,
                    "interval": interval
                },
                "facet_filter": {
                    "and": [{
                        "range": {
                            datefield: {
                                "from": datespan.startdate_display,
                                "to": datespan.enddate_display,
                            }}}]}}}}

    histo_data = es_query(params, q=q, size=0, es_url=ES_URLS["domains"])

    del q["facets"]
    q["filter"] = {
        "and": [
            {"range": {datefield: {"lt": datespan.startdate_display}}},
        ],
    }

    domains_before_date = es_query(params, q=q, size=0, es_url=ES_URLS["domains"])

    return {
        'histo_data': {"All Domains": histo_data["facets"]["histo"]["entries"]},
        'initial_values': {"All Domains": domains_before_date["hits"]["total"]},
        'startdate': datespan.startdate_key_utc,
        'enddate': datespan.enddate_key_utc,
    }
