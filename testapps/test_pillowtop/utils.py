from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from django.conf import settings
from django.test.utils import override_settings

from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.topics import get_multi_topic_offset
from corehq.util.decorators import ContextDecorator
from pillowtop import get_pillow_by_name
from pillowtop.pillow.interface import PillowBase


class process_pillow_changes(ContextDecorator):
    def __init__(self, pillow_name_or_instance=None, pillow_kwargs=None):
        self.pillows = []
        if pillow_name_or_instance:
            self.add_pillow(pillow_name_or_instance, pillow_kwargs)

    def add_pillow(self, pillow_name_or_instance, pillow_kwargs=None):
        if isinstance(pillow_name_or_instance, PillowBase):
            self.pillows.append(pillow_name_or_instance)
        else:
            self.pillows.append(self._get_pillow(pillow_name_or_instance, pillow_kwargs or {}))

    def _get_pillow(self, pillow_name, pillow_kwargs):
        with real_pillow_settings(), override_settings(PTOP_CHECKPOINT_DELAY_OVERRIDE=None):
            return get_pillow_by_name(pillow_name, instantiate=True, **pillow_kwargs)

    def __enter__(self):
        self.offsets = [
            pillow.get_change_feed().get_latest_offsets_as_checkpoint_value()
            for pillow in self.pillows
        ]

    def __exit__(self, exc_type, exc_val, exc_tb):
        for offsets, pillow in zip(self.offsets, self.pillows):
            pillow.process_changes(since=offsets, forever=False)


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
            client_id='test-{}'.format(uuid.uuid4().hex),
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
