from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from abc import ABCMeta, abstractproperty, abstractmethod
from datetime import datetime

import sys

from django.db.utils import DatabaseError, InterfaceError

from corehq.util.datadog.gauges import datadog_counter, datadog_gauge, datadog_histogram
from corehq.util.timer import TimingContext
from dimagi.utils.logging import notify_exception
from kafka.common import TopicAndPartition
from pillowtop.const import CHECKPOINT_MIN_WAIT
from pillowtop.dao.exceptions import DocumentMissingError
from pillowtop.utils import force_seq_int
from pillowtop.exceptions import PillowtopCheckpointReset
from pillowtop.logger import pillow_logging
import six


def _topic_for_ddog(topic):
    # can be a string for couch pillows, but otherwise is topic, partition
    if isinstance(topic, TopicAndPartition):
        return 'topic:{}-{}'.format(topic.topic, topic.partition)
    elif isinstance(topic, tuple) and len(topic) == 2:
        return 'topic:{}-{}'.format(topic[0], topic[1])
    else:
        return 'topic:{}'.format(topic)


class PillowRuntimeContext(object):
    """
    Runtime context for a pillow. Gets passed around during the processing methods
    so that other functions can use it without maintaining global state on the class.
    """

    def __init__(self, changes_seen=0):
        self.changes_seen = changes_seen


class PillowBase(six.with_metaclass(ABCMeta, object)):
    """
    This defines the external pillowtop API. Everything else should be considered a specialization
    on top of it.
    """

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

    def _update_checkpoint(self, change, context):
        if change and context:
            updated = self.update_checkpoint(change, context)
        else:
            updated = self.checkpoint.touch(min_interval=CHECKPOINT_MIN_WAIT)
        if updated:
            self._record_checkpoint_in_datadog()

    @property
    def _should_process_in_chunks(self):
        # chunked processing is only supported for pillows with single processor
        return (len(self.processors) == 1
            and getattr(self.processors[0], 'processor_chunk_size', 0) > 0)

    def process_changes(self, since, forever):
        # Pass changes from the feed to processors
        context = PillowRuntimeContext(changes_seen=0)
        min_wait_seconds = 30
        try:
            changes_chunk = []
            last_process_time = datetime.utcnow()
            for change in self.get_change_feed().iter_changes(since=since or None, forever=forever):
                context.changes_seen += 1
                if change:
                    if self._should_process_in_chunks:
                        changes_chunk.append(change)
                        chunk_full = len(changes_chunk) == self.processors[0].processor_chunk_size
                        time_elapsed = (datetime.utcnow() - last_process_time).seconds > min_wait_seconds
                        if chunk_full or time_elapsed:
                            last_process_time = datetime.utcnow()
                            self.process_chunk_with_error_handling(changes_chunk, context)
                            changes_chunk = []
                    else:
                        self.process_with_error_handling(change, context)
                else:
                    self._update_checkpoint(None, None)
            self.process_chunk_with_error_handling(changes_chunk, context)
        except PillowtopCheckpointReset:
            # finish processing any ramining chunk
            self.process_chunk_with_error_handling(changes_chunk, context)
            self.process_changes(since=self.get_last_checkpoint_sequence(), forever=forever)

    def process_chunk_with_error_handling(self, changes_chunk, context):
        """
        Passes given changes_chunk to the processor for chunked processing
            If there is an exception in chunked processing, falls back
            to passing changes one by one to the processor
        """
        if not changes_chunk:
            return
        retry_changes = set()
        timer = TimingContext()
        with timer:
            try:
                # chunked processing is supported if there is only one processor
                retry_changes = self.processors[0].process_changes_chunk(self, changes_chunk)
            except Exception as ex:
                notify_exception(
                    None,
                    "{pillow_name} Error in processing changes chunk {change_ids}: {ex}".format(
                        pillow_name=self.get_name(),
                        change_ids=[c.id for c in changes_chunk],
                        ex=ex
                    ))
                # fall back to processing one by one
                for change in changes_chunk:
                    self.process_with_error_handling(change, context, update_checkpoint=False)
            else:
                # fall back to processing one by one for failed changes
                for change in retry_changes:
                    self.process_with_error_handling(change, context, update_checkpoint=False)
        context.changes_seen += len(changes_chunk)
        # update checkpoint for just the latest change
        self._update_checkpoint(changes_chunk[-1], context)
        self._record_datadog_metrics(changes_chunk, retry_changes, timer)

    def _record_datadog_metrics(self, changes_chunk, retry_changes, timer):
        tags = ["pillow_name:{}".format(self.get_name()), "mode:chunked"]
        datadog_counter('commcare.change_feed.changes.count', len(changes_chunk), tags=tags)
        datadog_counter('commcare.change_feed.changes.exception', len(retry_changes), tags=tags)
        datadog_counter('commcare.change_feed.changes.suceess',
            len(set(changes_chunk) - set(retry_changes)), tags=tags)

        max_change_lag = (datetime.utcnow() - changes_chunk[0].metadata.publish_timestamp).seconds
        min_change_lag = (datetime.utcnow() - changes_chunk[-1].metadata.publish_timestamp).seconds
        datadog_gauge('commcare.change_feed.chunked.min_change_lag', min_change_lag, tags=tags)
        datadog_gauge('commcare.change_feed.chunked.max_change_lag', max_change_lag, tags=tags)

        datadog_histogram('commcare.change_feed.chunked.processing_time_total', timer.duration,
            tags=tags + ["chunk_size:{}".format(str(len(changes_chunk)))])
        datadog_histogram(
            'commcare.change_feed.processing_time',
            timer.duration / len(changes_chunk),
            tags=tags + ["chunk_size:".format(str(len(changes_chunk)))])

    def process_with_error_handling(self, change, context, update_checkpoint=True):
        timer = TimingContext()
        try:
            with timer:
                self.process_change(change)
        except Exception as ex:
            try:
                handle_pillow_error(self, change, ex)
            except Exception as e:
                notify_exception(None, 'processor error in pillow {} {}'.format(
                    self.get_name(), e,
                ))
                self._record_change_exception_in_datadog(change)
                raise
        else:
            if update_checkpoint:
                self._update_checkpoint(change, context)
                self._record_change_success_in_datadog(change)
        self._record_change_in_datadog(change, timer)

    @abstractmethod
    def process_change(self, change):
        pass

    @abstractmethod
    def update_checkpoint(self, change, context):
        """
        :return: True if checkpoint was updated otherwise False
        """
        pass

    def _normalize_checkpoint_sequence(self):
        if self.checkpoint is None:
            return {}

        sequence = self.get_last_checkpoint_sequence()
        return self._normalize_sequence(sequence)

    def _normalize_sequence(self, sequence):
        from pillowtop.feed.couch import CouchChangeFeed
        change_feed = self.get_change_feed()

        if not isinstance(sequence, dict):
            if isinstance(change_feed, CouchChangeFeed):
                topic = change_feed.couch_db
            else:
                return {}

            sequence = {topic: force_seq_int(sequence)}
        return sequence

    def _record_checkpoint_in_datadog(self):
        datadog_counter('commcare.change_feed.change_feed.checkpoint', tags=[
            'pillow_name:{}'.format(self.get_name()),
        ])
        checkpoint_sequence = self._normalize_checkpoint_sequence()
        for topic, value in six.iteritems(checkpoint_sequence):
            datadog_gauge('commcare.change_feed.checkpoint_offsets', value, tags=[
                'pillow_name:{}'.format(self.get_name()),
                _topic_for_ddog(topic),
            ])

    def _record_change_in_datadog(self, change, timer):
        self.__record_change_metric_in_datadog('commcare.change_feed.changes.count', change, timer)

    def _record_change_success_in_datadog(self, change):
        self.__record_change_metric_in_datadog('commcare.change_feed.changes.success', change)

    def _record_change_exception_in_datadog(self, change):
        self.__record_change_metric_in_datadog('commcare.change_feed.changes.exceptions', change)

    def __record_change_metric_in_datadog(self, metric, change, timer=None):
        if change.metadata is not None:
            tags = [
                'datasource:{}'.format(change.metadata.data_source_name),
                'is_deletion:{}'.format(change.metadata.is_deletion),
                'pillow_name:{}'.format(self.get_name()),
            ]
            datadog_counter(metric, tags=tags)

            change_lag = (datetime.utcnow() - change.metadata.publish_timestamp).seconds
            datadog_gauge('commcare.change_feed.change_lag', change_lag, tags=[
                'pillow_name:{}'.format(self.get_name()),
                _topic_for_ddog(change.topic),
            ])

            if timer:
                datadog_histogram('commcare.change_feed.processing_time', timer.duration, tags=tags)


class ChangeEventHandler(six.with_metaclass(ABCMeta, object)):
    """
    A change-event-handler object used in constructed pillows.
    """

    @abstractmethod
    def update_checkpoint(self, change, context):
        """
        :return: True if checkpoint was updated otherwise False
        """
        pass

    @abstractmethod
    def get_new_seq(self, change):
        """
        :return: appropriate sequence value to update the checkpoint to
        """
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
        if isinstance(processor, list):
            self.processors = processor
        else:
            self.processors = [processor]

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
        for processor in self.processors:
            processor.process_change(self, change)

    def update_checkpoint(self, change, context):
        if self._change_processed_event_handler is not None:
            return self._change_processed_event_handler.update_checkpoint(change, context)
        return False


def handle_pillow_error(pillow, change, exception):
    from pillow_retry.models import PillowError
    error_id = e = None

    # keep track of error attempt count
    change.increment_attempt_count()

    # always retry document missing errors, because the error is likely with couch
    if pillow.retry_errors or isinstance(exception, DocumentMissingError):
        try:
            error = PillowError.get_or_create(change, pillow)
        except (DatabaseError, InterfaceError) as e:
            error_id = 'PillowError.get_or_create failed'
        else:
            error.add_attempt(exception, sys.exc_info()[2], change.metadata)
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

    if e:
        raise e
