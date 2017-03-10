from abc import ABCMeta, abstractproperty, abstractmethod

import sys

from corehq.util.soft_assert import soft_assert
from corehq.util.datadog.gauges import datadog_counter, datadog_gauge
from corehq.util.timer import TimingContext
from dimagi.utils.logging import notify_exception
from pillowtop.const import CHECKPOINT_MIN_WAIT
from pillowtop.utils import force_seq_int
from pillowtop.exceptions import PillowtopCheckpointReset
from pillowtop.logger import pillow_logging


class PillowRuntimeContext(object):
    """
    Runtime context for a pillow. Gets passed around during the processing methods
    so that other functions can use it without maintaining global state on the class.
    """

    def __init__(self, changes_seen=0, do_set_checkpoint=True):
        self.changes_seen = changes_seen
        self.do_set_checkpoint = do_set_checkpoint


class PillowBase(object):
    """
    This defines the external pillowtop API. Everything else should be considered a specialization
    on top of it.
    """
    __metaclass__ = ABCMeta

    # set to true to disable saving pillow retry errors
    retry_errors = True

    @abstractproperty
    def pillow_id(self):
        """
        A unique ID for this pillow
        """
        pass

    @abstractproperty
    def document_store(self):
        """
        Returns a DocumentStore instance for retreiving documents.
        """
        pass

    @abstractproperty
    def checkpoint(self):
        """
        Returns a PillowCheckpoint instance dealing with checkpoints.
        """
        pass

    @abstractmethod
    def get_change_feed(self):
        """
        Returns a ChangeFeed instance for iterating changes.
        """
        pass

    @abstractmethod
    def get_name(self):
        pass

    def get_last_checkpoint_sequence(self):
        return self.checkpoint.get_or_create_wrapped().wrapped_sequence

    def get_checkpoint(self, verify_unchanged=False):
        return self.checkpoint.get_or_create_wrapped(verify_unchanged=verify_unchanged)

    def set_checkpoint(self, change):
        self.checkpoint.update_to(change['seq'])

    def reset_checkpoint(self):
        self.checkpoint.reset()

    def run(self):
        """
        Main entry point for running pillows forever.
        """
        pillow_logging.info("Starting pillow %s" % self.__class__)
        self.process_changes(since=self.get_last_checkpoint_sequence(), forever=True)

    def process_changes(self, since, forever):
        """
        Process changes from the changes stream.
        """
        context = PillowRuntimeContext(changes_seen=0, do_set_checkpoint=True)
        try:
            for change in self.get_change_feed().iter_changes(since=since, forever=forever):
                if change:
                    timer = TimingContext()
                    try:
                        context.changes_seen += 1
                        with timer:
                            self.process_with_error_handling(change)
                    except Exception as e:
                        notify_exception(None, u'processor error in pillow {} {}'.format(
                            self.get_name(), e,
                        ))
                        self._record_change_exception_in_datadog(change)
                        raise
                    else:
                        self.fire_change_processed_event(change, context)
                        self._record_change_success_in_datadog(change)
                    self._record_change_in_datadog(change, timer)
                else:
                    updated = self.checkpoint.touch(min_interval=CHECKPOINT_MIN_WAIT)
                    if updated:
                        self._record_checkpoint_in_datadog()
        except PillowtopCheckpointReset:
            self.process_changes(since=self.get_last_checkpoint_sequence(), forever=forever)

    def process_with_error_handling(self, change):
        try:
            self.process_change(change)
        except Exception as ex:
            handle_pillow_error(self, change, ex)

    @abstractmethod
    def process_change(self, change):
        pass

    @abstractmethod
    def fire_change_processed_event(self, change, context):
        pass

    def _normalize_checkpoint_sequence(self):
        from pillowtop.feed.couch import CouchChangeFeed
        from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed

        if self.checkpoint is None:
            return {}

        sequence = self.get_last_checkpoint_sequence()
        change_feed = self.get_change_feed()

        if not isinstance(sequence, dict):
            if isinstance(change_feed, KafkaChangeFeed):
                topics = change_feed.topics
                assert len(topics) == 1
                topic = topics[0]
            elif isinstance(change_feed, CouchChangeFeed):
                topic = change_feed.couch_db
            else:
                return {}

            sequence = {topic: force_seq_int(sequence)}
        return sequence

    def _record_checkpoint_in_datadog(self):
        datadog_counter('commcare.change_feed.change_feed.checkpoint', tags=[
            'pillow_name:{}'.format(self.get_name()),
        ])

    def _record_change_in_datadog(self, change, timer):
        change_feed = self.get_change_feed()
        sequence = self._normalize_checkpoint_sequence()
        current_offsets = change_feed.get_current_offsets()

        for topic, value in sequence.iteritems():
            datadog_gauge('commcare.change_feed.processed_offsets', value, tags=[
                'pillow_name:{}'.format(self.get_name()),
                'topic:{}'.format(topic),
            ])
            if topic in current_offsets:
                datadog_gauge('commcare.change_feed.need_processing', current_offsets[topic] - value, tags=[
                    'pillow_name:{}'.format(self.get_name()),
                    'topic:{}'.format(topic),
                ])

        for topic, offset in current_offsets.iteritems():
            datadog_gauge('commcare.change_feed.current_offsets', offset, tags=[
                'pillow_name:{}'.format(self.get_name()),
                'topic:{}'.format(topic),
            ])

        self.__record_change_metric_in_datadog('commcare.change_feed.changes.count', change, timer)

    def _record_change_success_in_datadog(self, change):
        self.__record_change_metric_in_datadog('commcare.change_feed.changes.success', change)

    def _record_change_exception_in_datadog(self, change):
        self.__record_change_metric_in_datadog('commcare.change_feed.changes.exceptions', change)

    def __record_change_metric_in_datadog(self, metric, change, timer=None):
        if change.metadata is not None:
            tags = [
                'datasource:{}'.format(change.metadata.data_source_name),
                'document_type:{}'.format(change.metadata.document_type),
                'domain:{}'.format(change.metadata.domain),
                'is_deletion:{}'.format(change.metadata.is_deletion),
                'pillow_name:{}'.format(self.get_name())
            ]
            datadog_counter(metric, tags=tags)

            if timer:
                datadog_gauge('commcare.change_feed.processing_time', timer.duration, tags=tags)


class ChangeEventHandler(object):
    """
    A change-event-handler object used in constructed pillows.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def fire_change_processed(self, change, context):
        pass


class ConstructedPillow(PillowBase):
    """
    An almost-implemented Pillow that relies on being passed the various constructor
    arguments it needs.
    """

    def __init__(self, name, checkpoint, change_feed, processor,
                 change_processed_event_handler=None):
        self._name = name
        self._checkpoint = checkpoint
        self._change_feed = change_feed
        self._processor = processor
        self._change_processed_event_handler = change_processed_event_handler

    @property
    def pillow_id(self):
        return self._name

    def get_name(self):
        return self._name

    def document_store(self):
        raise NotImplementedError()

    @property
    def checkpoint(self):
        return self._checkpoint

    def get_change_feed(self):
        return self._change_feed

    def process_change(self, change):
        self._processor.process_change(self, change)

    def fire_change_processed_event(self, change, context):
        if self._change_processed_event_handler is not None:
            self._change_processed_event_handler.fire_change_processed(change, context)


def handle_pillow_error(pillow, change, exception):
    from pillow_retry.models import PillowError
    error_id = None
    if pillow.retry_errors:
        error = PillowError.get_or_create(change, pillow)
        error.add_attempt(exception, sys.exc_info()[2])
        error.save()
        error_id = error.id

    pillow_logging.exception(
        "[%s] Error on change: %s, %s. Logged as: %s" % (
            pillow.get_name(),
            change['id'],
            exception,
            error_id
        )
    )
