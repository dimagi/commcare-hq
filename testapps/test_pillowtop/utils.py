import uuid

from django.conf import settings
from django.test.utils import override_settings

from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.topics import get_topic_offset, get_multi_topic_offset

from corehq.util.decorators import ContextDecorator
from pillowtop import get_pillow_by_name


class process_kafka_changes(ContextDecorator):
    def __init__(self, pillow_name_or_instance):
        if isinstance(pillow_name_or_instance, basestring):
            with real_pillow_settings(), override_settings(PTOP_CHECKPOINT_DELAY_OVERRIDE=None):
                self.pillow = get_pillow_by_name(pillow_name_or_instance, instantiate=True)
        else:
            self.pillow = pillow_name_or_instance

        self.topics = self.pillow.get_change_feed().topics

    def __enter__(self):
        if len(self.topics) == 1:
            self.kafka_seq = get_topic_offset(self.topics[0])
        else:
            self.kafka_seq = get_multi_topic_offset(self.topics)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pillow.process_changes(since=self.kafka_seq, forever=False)


class process_couch_changes(ContextDecorator):
    def __init__(self, pillow_name):
        with real_pillow_settings():
            self.pillow = get_pillow_by_name(pillow_name, instantiate=True)

    def __enter__(self):
        self.seq = self.pillow.get_change_feed().get_latest_change_id()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.pillow.process_changes(since=self.seq, forever=False)


class real_pillow_settings(ContextDecorator):
    def __enter__(self):
        self._PILLOWTOPS = settings.PILLOWTOPS
        if not settings.PILLOWTOPS:
            # assumes HqTestSuiteRunner, which blanks this out and saves a copy here
            settings.PILLOWTOPS = settings._PILLOWTOPS

    def __exit__(self, exc_type, exc_val, exc_tb):
        settings.PILLOWTOPS = self._PILLOWTOPS


class capture_kafka_changes_context(object):
    def __init__(self, *topics):
        self.topics = topics
        self.change_feed = KafkaChangeFeed(
            topics=topics,
            group_id='test-{}'.format(uuid.uuid4().hex),
        )
        self.changes = None

    def __enter__(self):
        self.kafka_seq = get_multi_topic_offset(self.topics)
        self.changes = []
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for change in self.change_feed.iter_changes(since=self.kafka_seq, forever=False):
            if change:
                self.changes.append(change)
