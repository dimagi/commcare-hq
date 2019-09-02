
import re
import traceback

from django.conf import settings
from django.db.utils import OperationalError
from six import string_types
from six.moves import filter

from corehq.util.cache_utils import is_rate_limited
from corehq.util.datadog.gauges import datadog_counter

RATE_LIMITED_EXCEPTIONS = {
    'dimagi.utils.couch.bulk.BulkFetchException': 'couchdb',
    'socketpool.pool.MaxTriesError': 'couchdb',

    'corehq.elastic.ESError': 'elastic',
    'elasticsearch.exceptions.ConnectionTimeout': 'elastic',
    'TransportError': 'elastic',

    'OperationalError': 'postgres',  # could be psycopg2._psycopg or django.db.utils

    'socket.error': 'rabbitmq',

    'redis.exceptions.ConnectionError': 'redis',
    'ClusterDownError': 'redis',

    'botocore.exceptions.ClientError': 'blobdb',
    'botocore.vendored.requests.packages.urllib3.exceptions.ProtocolError': 'blobdb',
    'botocore.vendored.requests.exceptions.ReadTimeout': 'blobdb',

    'celery.beat.SchedulingError': 'celery-beat',

    'corehq.form_processor.exceptions.KafkaPublishingError': 'kafka',
}


RATE_LIMIT_BY_PACKAGE = {
    # exception: (python package prefix, rate limit key)
    'requests.exceptions.ConnectionError': ('cloudant', 'couchdb'),
    'requests.exceptions.HTTPError': ('cloudant', 'couchdb'),
    'builtins.BrokenPipeError': ('amqp', 'rabbitmq'),
}


def _get_rate_limit_key(exc_info):
    exc_type, value, tb = exc_info
    exc_name = '%s.%s' % (exc_type.__module__, exc_type.__name__)
    if exc_type.__name__ in RATE_LIMITED_EXCEPTIONS:
        return RATE_LIMITED_EXCEPTIONS[exc_type.__name__]
    elif exc_name in RATE_LIMITED_EXCEPTIONS:
        return RATE_LIMITED_EXCEPTIONS[exc_name]

    if exc_name in RATE_LIMIT_BY_PACKAGE:
        # not super happy with this approach but want to be able to
        # rate limit exceptions based on where they come from rather than
        # the specific exception
        package, key = RATE_LIMIT_BY_PACKAGE[exc_name]
        frame_summaries = traceback.extract_tb(tb)
        for frame in frame_summaries:
            if frame[0].startswith(package): # filename
                return key


def is_pg_cancelled_query_exception(e):
    PG_QUERY_CANCELLATION_ERR_MSG = "canceling statement due to conflict with recovery"
    return isinstance(e, OperationalError) and PG_QUERY_CANCELLATION_ERR_MSG in e.message


class HQSanitzeSystemPasswords(object):
    MASK = '*' * 8

    def __init__(self):
        couch_database_passwords = set(filter(None, [
            db['COUCH_PASSWORD'] for db in settings.COUCH_DATABASES.values()
        ]))
        self._regex = re.compile('({})'.format('|'.join(
            couch_database_passwords
        )))

    def __call__(self, event):
        if 'exception' in event and 'values' in event['exception']:
            # sentry's data structure is rather silly/complicated
            for value in event['exception']['values'] or []:
                if 'value' in value:
                    value['value'] = self.sanitize('value', value['value'])
        return event

    def sanitize(self, key, value):
        if value and isinstance(value, string_types):
            return self._regex.sub(self.MASK, value)
        return value


sanitize_system_passwords = HQSanitzeSystemPasswords()


def _rate_limit_exc(exc_info):
    exc_type, exc_value, tb = exc_info
    rate_limit_key = _get_rate_limit_key(exc_info)
    if not rate_limit_key:
        return False

    datadog_counter('commcare.sentry.errors.rate_limited', tags=[
        'service:{}'.format(rate_limit_key)
    ])
    if is_pg_cancelled_query_exception(exc_value):
        datadog_counter('hq_custom.postgres.standby_query_canellations')
    exponential_backoff_key = '{}_down'.format(rate_limit_key)
    return is_rate_limited(exponential_backoff_key)


def before_sentry_send(event, hint):
    event = sanitize_system_passwords(event)
    if 'exc_info' not in hint:
        return event

    exc_type, exc_value, tb = hint['exc_info']

    if isinstance(exc_value, KeyboardInterrupt):
        return

    capture = getattr(exc_value, 'sentry_capture', True)
    if not capture:
        return

    if not _rate_limit_exc(hint['exc_info']):
        return event
