from django.conf import settings

from corehq.apps.change_feed.tests.utils import get_current_kafka_seq

from corehq.util.decorators import ContextDecorator
from pillowtop import get_pillow_by_name


class process_kafka_changes(ContextDecorator):
    def __init__(self, pillow_name, topic):
        self.topic = topic
        with real_pillow_settings():
            self.pillow = get_pillow_by_name(pillow_name, instantiate=True)

    def __enter__(self):
        self.kafka_seq = get_current_kafka_seq(self.topic)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pillow.process_changes(since=self.kafka_seq, forever=False)


class real_pillow_settings(ContextDecorator):
    def __enter__(self):
        self._PILLOWTOPS = settings.PILLOWTOPS
        if not settings.PILLOWTOPS:
            # assumes HqTestSuiteRunner, which blanks this out and saves a copy here
            settings.PILLOWTOPS = settings._PILLOWTOPS

    def __exit__(self, exc_type, exc_val, exc_tb):
        settings.PILLOWTOPS = self._PILLOWTOPS
