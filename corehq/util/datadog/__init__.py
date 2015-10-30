from django.conf import settings
import logging

logger = logging.getLogger(__name__)

try:
    from datadog.dogstatsd.base import DogStatsd
    use_real_statsd = True
except ImportError:
    use_real_statsd = False


class Callable(object):
    def __init__(self, name, ret=None):
        self.name = name
        self.ret = ret

    def __call__(self, *args, **kwargs):
        logger.debug("mock call: statsd.%s(*%s, **%s)", self.name, args, kwargs)
        return self.ret


class MockStatsd(object):
    def __getattribute__(self, item):
        if item == 'timed':
            def no_op_decorator(fn):
                return fn
            return Callable(item, ret=no_op_decorator)
        return Callable(item)


if use_real_statsd:
    statsd = DogStatsd(constant_tags=[
        'environment:{}'.format(settings.SERVER_ENVIRONMENT)
    ])
else:
    statsd = MockStatsd()
