from __future__ import absolute_import, unicode_literals
from six import string_types
from six.moves import filter
import re
from django.conf import settings
from raven.contrib.django import DjangoClient
from raven.processors import SanitizePasswordsProcessor

from corehq.util.cache_utils import is_rate_limited
from corehq.util.datadog.gauges import datadog_counter

RATE_LIMITED_EXCEPTIONS = {
    'botocore.vendored.requests.packages.urllib3.exceptions.ProtocolError': 'riak',
    'botocore.vendored.requests.exceptions.ReadTimeout': 'riak',
    'botocore.exceptions.ClientError': 'riak',
    'OperationalError': 'postgres',  # could be psycopg2._psycopg or django.db.utils
    'socket.error': 'rabbitmq',
    'redis.exceptions.ConnectionError': 'redis',
    'restkit.errors.RequestError': 'couchdb',
    'restkit.errors.RequestFailed': 'couchdb',
    'dimagi.utils.couch.bulk.BulkFetchException': 'couchdb',
    'socketpool.pool.MaxTriesError': 'couchdb',
    'corehq.elastic.ESError': 'elastic',
}


def _get_rate_limit_key(exc_info):
    exc_type = exc_info[0]
    exc_name = '%s.%s' % (exc_type.__module__, exc_type.__name__)
    if exc_type.__name__ in RATE_LIMITED_EXCEPTIONS:
        return RATE_LIMITED_EXCEPTIONS[exc_type.__name__]
    elif exc_name in RATE_LIMITED_EXCEPTIONS:
        return RATE_LIMITED_EXCEPTIONS[exc_name]


class HQSanitzeSystemPasswordsProcessor(SanitizePasswordsProcessor):
    def __init__(self, client):
        super(HQSanitzeSystemPasswordsProcessor, self).__init__(client)
        couch_database_passwords = set(filter(None, [
            db['COUCH_PASSWORD'] for db in settings.COUCH_DATABASES.values()
        ]))
        self._regex = re.compile('({})'.format('|'.join(
            couch_database_passwords
        )))

    def sanitize(self, key, value):
        value = super(HQSanitzeSystemPasswordsProcessor, self).sanitize(key, value)
        if value and isinstance(value, string_types):
            return self._regex.sub(self.MASK, value)
        return value

    def process(self, data, **kwargs):
        data = super(HQSanitzeSystemPasswordsProcessor, self).process(data, **kwargs)
        if 'exception' in data and 'values' in data['exception']:
            # sentry's data structure is rather silly/complicated
            for value in data['exception']['values'] or []:
                if 'value' in value:
                    value['value'] = self.sanitize('value', value['value'])
        return data


class HQSentryClient(DjangoClient):

    def should_capture(self, exc_info):
        ex_value = exc_info[1]
        capture = getattr(ex_value, 'sentry_capture', True)
        if not capture:
            return False

        if not super(HQSentryClient, self).should_capture(exc_info):
            return False

        rate_limit_key = _get_rate_limit_key(exc_info)
        if rate_limit_key:
            datadog_counter('commcare.sentry.errors.rate_limited', tags=[
                'service:{}'.format(rate_limit_key)
            ])
            exponential_backoff_key = '{}_down'.format(rate_limit_key)
            return not is_rate_limited(exponential_backoff_key)
        return True
