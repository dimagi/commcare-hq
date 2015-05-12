from dateutil.parser import parse
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.sms.models import CallLog, INCOMING, OUTGOING
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.couch.database import iter_docs
from math import ceil
from optparse import make_option
import pytz


UNKNOWN = '?'


def get_ids(start_date=None, timezone=None):
    result = CallLog.view(
        'sms/call_by_session',
        include_docs=False,
    ).all()
    def include_row(row):
        if start_date:
            date = row['key'][1]
            if date:
                date = parse(date).replace(tzinfo=None)
                date = get_naive_user_datetime(date, timezone=timezone)
                return date >= start_date
            else:
                return False
        return True
    return [row['id'] for row in result if include_row(row)]


def get_naive_user_datetime(date, timezone=None):
    if date and timezone:
        date = ServerTime(date).user_time(timezone).done().replace(tzinfo=None)
    return date


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
        data[backend_api] = {
            INCOMING: {'calls': 0, 'minutes': 0},
            OUTGOING: {'calls': 0, 'minutes': 0},
            UNKNOWN: {'calls': 0, 'minutes': 0},
        }
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


def get_direction(call):
    return {
        INCOMING: INCOMING,
        OUTGOING: OUTGOING,
    }.get(call.direction, UNKNOWN)


def get_data(ids, timezone=None):
    """
    returns the data in the format:
    {
        '2015-03': {
            'domain1': {
                'KOOKOO': {
                    'I': {'calls': 2, 'minutes': 3},
                    'O': {'calls': 40, 'minutes': 45},
                    '?': {'calls': 0, 'minutes': 0},
                 },
            },
            'domain2': {
                'KOOKOO': {
                    'I': {'calls': 1, 'minutes': 1},
                    'O': {'calls': 20, 'minutes': 25},
                    '?': {'calls': 0, 'minutes': 0},
                 },
                'TELERIVET': {
                    'I': {'calls': 10, 'minutes': 0},
                    'O': {'calls': 0, 'minutes': 0},
                    '?': {'calls': 0, 'minutes': 0},
                 },
            }
        }
    }
    """
    data = {}
    for doc in iter_docs(CallLog.get_db(), ids):
        call = CallLog.wrap(doc)
        date = get_naive_user_datetime(call.date, timezone=timezone)
        month_data = get_month_data(data, date)
        domain_data = get_domain_data(month_data, call.domain)
        backend_api = get_backend_api(call)
        backend_data = get_backend_data(domain_data, backend_api)
        direction = get_direction(call)
        backend_data[direction]['calls'] += 1
        duration = (call.duration or 0) / 60.0
        duration = int(ceil(duration))
        backend_data[direction]['minutes'] += duration
    return data


class Command(BaseCommand):
    """
    Usage: python manage.py ivr_usage [start_date] [--timezone timezone]
    """
    args = 'start_date'
    help = ('A simple script to calculate IVR usage. '
        'Eventually, this will be ported to the billing framework.')
    option_list = BaseCommand.option_list + (
        make_option('--timezone',
                    action='store',
                    type='string',
                    dest='timezone',
                    default=None,
                    help=('Specify to interpret month start and end '
                        'times using this timezone.')),
    )

    def handle(self, *args, **options):
        try:
            timezone = pytz.timezone(options['timezone'])
        except:
            print 'Warning: Timezone not recognized, using UTC instead'
            timezone = None

        if len(args) == 0:
            start_date = None
        else:
            try:
                start_date = parse(args[0]).replace(tzinfo=None)
            except:
                raise CommandError('Start date must be YYYY-MM-DD')

        print 'Month,Domain,Backend,Direction,Num Calls,Minutes Used'
        ids = get_ids(start_date, timezone=timezone)
        data = get_data(ids, timezone=timezone)
        for (month, month_data) in data.iteritems():
            for (domain, domain_data) in month_data.iteritems():
                for (backend, backend_data) in domain_data.iteritems():
                    for (direction, direction_data) in backend_data.iteritems():
                        print '%s,%s,%s,%s,%s,%s' % (month, domain, backend, direction,
                            direction_data['calls'], direction_data['minutes'])
