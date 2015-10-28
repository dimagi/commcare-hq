from functools import wraps
from corehq.util.datadog import statsd
import logging

logger = logging.getLogger(__name__)


def count_by_response_code(metric_prefix):
    def _wrapper(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            response = fn(*args, **kwargs)

            try:
                metric_name = '{}.{}'.format(metric_prefix, response.status_code)
                statsd.increment(metric_name)
            except Exception:
                logger.exception('Unable to record Datadog stats')

            return response

        return _inner
    return _wrapper
