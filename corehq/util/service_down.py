from corehq.util.cache_utils import ExponentialBackoff
from corehq.util.global_request import get_request
from dimagi.utils.logging import notify_exception


def notify_service_down(message, exponential_backoff_key):

    count = ExponentialBackoff.increment(exponential_backoff_key)
    if not ExponentialBackoff.should_backoff(exponential_backoff_key):
        notify_exception(get_request(), message, details={
            'count': count,
        })


def notify_riak_down():
    notify_service_down(
        message="Riak is struggling or down",
        exponential_backoff_key='riak_down',
    )
