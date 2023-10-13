import inspect
import logging
import re
import traceback
from types import TracebackType

from django.conf import settings
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.utils import CursorWrapper
from django.db.utils import OperationalError

from corehq.util.cache_utils import is_rate_limited
from corehq.util.metrics import metrics_counter

logger = logging.getLogger(__name__)


RATE_LIMITED_EXCEPTIONS = {
    'dimagi.utils.couch.bulk.BulkFetchException': 'couchdb',
    'socketpool.pool.MaxTriesError': 'couchdb',

    'corehq.elastic.ESError': 'elastic',
    'elasticsearch.exceptions.ConnectionTimeout': 'elastic',
    'TransportError': 'elastic',

    'OperationalError': 'postgres',  # could be psycopg2._psycopg or django.db.utils

    'kombu.connection.OperationalError': 'rabbitmq',
    'socket.error': 'rabbitmq',

    'redis.exceptions.ConnectionError': 'redis',
    'ClusterDownError': 'redis',

    'botocore.exceptions.ClientError': 'blobdb',
    'botocore.vendored.requests.packages.urllib3.exceptions.ProtocolError': 'blobdb',
    'botocore.vendored.requests.exceptions.ReadTimeout': 'blobdb',

    'celery.beat.SchedulingError': 'celery-beat',

    'corehq.form_processor.exceptions.KafkaPublishingError': 'kafka',
    'kafka.errors.IllegalStateError': 'kafka',

    'GreenletExit': 'greenletexit',
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
    if exc_name in RATE_LIMITED_EXCEPTIONS:
        return RATE_LIMITED_EXCEPTIONS[exc_name]
    elif exc_type.__name__ in RATE_LIMITED_EXCEPTIONS:
        return RATE_LIMITED_EXCEPTIONS[exc_type.__name__]

    if exc_name in RATE_LIMIT_BY_PACKAGE:
        # not super happy with this approach but want to be able to
        # rate limit exceptions based on where they come from rather than
        # the specific exception
        package, key = RATE_LIMIT_BY_PACKAGE[exc_name]
        frame_summaries = traceback.extract_tb(tb)
        for frame in frame_summaries:
            if frame.filename.startswith(package):
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
        if value and isinstance(value, str):
            return self._regex.sub(self.MASK, value)
        return value


sanitize_system_passwords = HQSanitzeSystemPasswords()


def subtype_error(tb: TracebackType, rate_limit_key: str) -> str:
    if rate_limit_key == 'postgres':
        f_locals = inspect.getinnerframes(tb)[-1].frame.f_locals
        dsn = None
        if f_locals.get('dsn'):
            dsn = f_locals['dsn']
        elif f_locals.get('cursor'):
            dsn = f_locals['cursor'].connection.dsn
        elif f_locals.get('self'):
            frame_self = f_locals['self']
            if isinstance(frame_self, BaseDatabaseWrapper):
                dsn = frame_self.connection.dsn
            if isinstance(frame_self, CursorWrapper):
                dsn = frame_self.db.connection.dsn

        if not dsn:
            return rate_limit_key

        conf = dict([field.split('=') for field in dsn.split(' ')])
        return f"{rate_limit_key}_{conf['dbname']}"
    return rate_limit_key


def _rate_limit_exc(exc_info):
    exc_type, exc_value, tb = exc_info
    rate_limit_key = _get_rate_limit_key(exc_info)
    if not rate_limit_key:
        return False

    try:
        rate_limit_key = subtype_error(tb, rate_limit_key)
    except Exception:
        logger.exception("Error while subtyping rate limited error")

    metrics_counter('commcare.sentry.errors.rate_limited', tags={
        'service': rate_limit_key
    })
    if is_pg_cancelled_query_exception(exc_value):
        metrics_counter('commcare.postgres.standby_query_canellations')
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
