from dateutil.parser import parse
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.sms.models import CallLog
from dimagi.utils.couch.database import iter_docs
from math import ceil


def get_ids(start_date=None):
    result = CallLog.view(
        'sms/call_by_session',
        include_docs=False,
    ).all()
    def include_row(row):
        if start_date:
            try:
                date = parse(row['key'][1]).replace(tzinfo=None)
            except:
                return False
            return date >= start_date
        return True
    return [row['id'] for row in result if include_row(row)]


def get_month_data(data, date):
    try:
        date_month = date.strftime('%Y-%m')
    except:
        date_month = 'catchall'
    if date_month not in data:
        data[date_month] = {}
    return data[date_month]


def get_domain_data(data, domain):
    domain = domain or 'catchall'
    if domain not in data:
        data[domain] = {}
    return data[domain]


def get_backend_data(data, backend_api):
    if backend_api not in data:
        data[backend_api] = {'calls': 0, 'minutes': 0}
    return data[backend_api]


def get_backend_api(call):
    backend_api = call.backend_api
    if not backend_api:
        if call.gateway_session_id:
            if call.gateway_session_id.startswith('TELERIVET'):
                backend_api = 'TELERIVET'
            elif call.gateway_session_id.startswith('TROPO'):
                backend_api = 'TROPO'
    return backend_api or 'catchall'


def get_data(ids):
    """
    returns the data in the format:
    {
        '2015-03': {
            'domain1': {
                'KOOKOO': {'calls': 40, 'minutes': 45}
            },
            'domain2': {
                'KOOKOO': {'calls': 20, 'minutes': 25}
                'TELERIVET': {'calls': 5, 'minutes': 0}
            }
        }
    }
    """
    data = {}
    for doc in iter_docs(CallLog.get_db(), ids):
        call = CallLog.wrap(doc)
        month_data = get_month_data(data, call.date)
        domain_data = get_domain_data(month_data, call.domain)
        backend_api = get_backend_api(call)
        backend_data = get_backend_data(domain_data, backend_api)
        backend_data['calls'] += 1
        duration = (call.duration or 0) / 60.0
        duration = int(ceil(duration))
        backend_data['minutes'] += duration
    return data


class Command(BaseCommand):
    """
    Usage: python manage.py ivr_usage [start_date]
    """
    args = 'start_date'
    help = ('A simple script to calculate IVR usage. '
        'Eventually, this will be ported to the billing framework.')

    def handle(self, *args, **options):
        if len(args) == 0:
            start_date = None
        else:
            try:
                start_date = parse(args[0]).replace(tzinfo=None)
            except:
                raise CommandError('Start date must be YYYY-MM-DD')

        print 'Month,Domain,Backend,Num Calls,Minutes Used'
        data = get_data(get_ids(start_date))
        for (month, month_data) in data.iteritems():
            for (domain, domain_data) in month_data.iteritems():
                for (backend, backend_data) in domain_data.iteritems():
                    print '%s,%s,%s,%s,%s' % (month, domain, backend,
                        backend_data['calls'], backend_data['minutes'])
