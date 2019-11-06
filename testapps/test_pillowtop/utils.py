import uuid
from datetime import datetime

from django.conf import settings
from django.db.models import Max
from django.test.utils import override_settings

from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.models import PostgresPillowCheckpoint
from corehq.apps.change_feed.topics import get_multi_topic_offset
from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.decorators import ContextDecorator
from pillowtop import get_pillow_by_name
from pillowtop.pillow.interface import PillowBase, PostgresPillow


class process_pillow_changes(ContextDecorator):
    def __init__(self, pillow_name_or_instance=None, pillow_kwargs=None):
        self._pillows = []
        self.pillow_names_or_instances = []
        if pillow_name_or_instance:
            self.pillow_names_or_instances.append((pillow_name_or_instance, pillow_kwargs))
        self._populated = False

    def add_pillow(self, pillow_name_or_instance, pillow_kwargs=None):
        self.pillow_names_or_instances.append((pillow_name_or_instance, pillow_kwargs))

    def _get_pillow(self, pillow_name, pillow_kwargs):
        with real_pillow_settings(), override_settings(PTOP_CHECKPOINT_DELAY_OVERRIDE=None):
            return get_pillow_by_name(pillow_name, instantiate=True, **pillow_kwargs)

    def _populate(self):
        if not self._populated:
            for pillow_name_or_instance, pillow_kwargs in self.pillow_names_or_instances:
                if isinstance(pillow_name_or_instance, PillowBase):
                    self._pillows.append(pillow_name_or_instance)
                else:
                    self._pillows.append(self._get_pillow(pillow_name_or_instance, pillow_kwargs or {}))
            self._populated = True
        else:
            assert len(self.pillow_names_or_instances) == len(self._pillows), 'Pillows added after first use'

    def __enter__(self):
        self._populate()
        self.offsets = []
        for pillow in self._pillows:
            if isinstance(pillow, PostgresPillow):
                for db_alias in get_db_aliases_for_partitioned_query():
                    PostgresPillowCheckpoint.objects.get_or_create(
                        pillow_id=pillow.get_name(),
                        db_alias=db_alias,
                        model='corehq.form_processor.models.XFormInstanceSQL',
                        defaults={
                            'remainder': 0,
                            'update_sequence_id': (
                                XFormInstanceSQL.objects.using(db_alias)
                                .aggregate(Max('update_sequence_id'))['update_sequence_id__max'] or 0
                            ),
                            'last_server_modified_on': datetime.utcnow(),
                        }
                    )
                self.offsets.append(None)
            else:
                self.offsets.append(
                    pillow.get_change_feed().get_latest_offsets_as_checkpoint_value()
                )

    def __exit__(self, exc_type, exc_val, exc_tb):
        for offsets, pillow in zip(self.offsets, self._pillows):
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
