from functools import wraps
from corehq.util.datadog import statsd, COMMON_TAGS, datadog_logger
from datadog import api


from corehq.util.datadog.const import ALERT_INFO


def count_by_response_code(metric_prefix):
    def _wrapper(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            response = fn(*args, **kwargs)

            try:
                metric_name = '{}.{}'.format(metric_prefix, response.status_code)
                statsd.increment(metric_name)
            except Exception:
                datadog_logger.exception('Unable to record Datadog stats')

            return response

        return _inner
    return _wrapper


def datadog_initialized():
    return api._api_key and api._application_key


def create_datadog_event(title, text, alert_type=ALERT_INFO, tags=None, aggregation_key=None):
    tags = COMMON_TAGS + (tags or [])
    if datadog_initialized():
        api.Event.create(
            title=title, text=text, tags=tags,
            alert_type=alert_type, aggregation_key=aggregation_key,
        )
    else:
        datadog_logger.debug('Datadog event: (%s) %s\n%s', alert_type, title, text)
