from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from abc import ABCMeta, abstractproperty, abstractmethod
from collections import Counter
from datetime import datetime

from django.conf import settings
from memoized import memoized

import sys

from corehq.util.datadog.gauges import datadog_counter, datadog_gauge, datadog_histogram
from corehq.util.timer import TimingContext
from dimagi.utils.logging import notify_exception
from kafka.common import TopicPartition
from pillowtop.const import CHECKPOINT_MIN_WAIT
from pillowtop.dao.exceptions import DocumentMissingError
from pillowtop.utils import force_seq_int
from pillowtop.exceptions import PillowtopCheckpointReset
from pillowtop.logger import pillow_logging
import six


def _topic_for_ddog(topic):
    # can be a string for couch pillows, but otherwise is topic, partition
    if isinstance(topic, TopicPartition):
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
    # this will be the batch size for processors that support batch processing
    processor_chunk_size = 0

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
    @memoized
    def batch_processors(self):
        if self.processor_chunk_size:
            return [processor for processor in self.processors if processor.supports_batch_processing]
        else:
            return []

    @property
    @memoized
    def serial_processors(self):
        if self.processor_chunk_size:
            return [processor for processor in self.processors if not processor.supports_batch_processing]
        else:
            return self.processors

    def process_changes(self, since, forever):
        """
        Process changes on all the pillow processors.

            Processes changes serially on serial processors, and in batches on
            batch processors. If there are batch processors, checkpoint is updated
            at the end of the batch, otherwise is updated for every change.
        """
        context = PillowRuntimeContext(changes_seen=0)
        min_wait_seconds = 30

        def process_offset_chunk(chunk, context):
            if not chunk:
                return
            self._batch_process_with_error_handling(chunk)
            self._update_checkpoint(chunk[-1], context)

        # keep track of chunk for batch processors
        changes_chunk = []
        last_process_time = datetime.utcnow()

        try:
            for change in self.get_change_feed().iter_changes(since=since or None, forever=forever):
                context.changes_seen += 1
                if change:
                    if self.batch_processors:
                        # Queue and process in chunks for both batch
                        #   and serial processors
                        changes_chunk.append(change)
                        chunk_full = len(changes_chunk) == self.processor_chunk_size
                        time_elapsed = (datetime.utcnow() - last_process_time).seconds > min_wait_seconds
                        if chunk_full or time_elapsed:
                            last_process_time = datetime.utcnow()
                            self._batch_process_with_error_handling(changes_chunk)
                            # update checkpoint for just the latest change
                            self._update_checkpoint(changes_chunk[-1], context)
                            # reset for next chunk
                            changes_chunk = []
                    else:
                        # process all changes one by one
                        processing_time = self.process_with_error_handling(change)
                        self._record_change_in_datadog(change, processing_time)
                        self._update_checkpoint(change, context)
                else:
                    self._update_checkpoint(None, None)
            process_offset_chunk(changes_chunk, context)
        except PillowtopCheckpointReset:
            process_offset_chunk(changes_chunk, context)
            self.process_changes(since=self.get_last_checkpoint_sequence(), forever=forever)

    def _batch_process_with_error_handling(self, changes_chunk):
        """
        Process given chunk in batch mode first on batch-processors
            and only latter on serial processors one by one, so that
            docs can be fetched only once while batch processing in bulk
            and cached via change.get_document for serial processors.
            For the relookup to be avoided at least one batch processor under
            should use change.set_document after docs are fetched in bulk

            If there is an exception in chunked processing, falls back
            to serial processing.
        """
        processing_time = 0

        def reprocess_serially(chunk, processor):
            for change in chunk:
                self.process_with_error_handling(change, processor)

        for processor in self.batch_processors:
            if not changes_chunk:
                return set(), 0

            changes_chunk = self._deduplicate_changes(changes_chunk)
            retry_changes = set()
            timer = TimingContext()
            with timer:
                try:
                    retry_changes, change_exceptions = processor.process_changes_chunk(changes_chunk)
                except Exception as ex:
                    notify_exception(
                        None,
                        "{pillow_name} Error in processing changes chunk {change_ids}: {ex}".format(
                            pillow_name=self.get_name(),
                            change_ids=[c.id for c in changes_chunk],
                            ex=ex
                        ))
                    self._record_batch_exception_in_datadog(processor)
                    for change in set(changes_chunk) - set(retry_changes):
                        self._record_change_success_in_datadog(change, processor)
                    # fall back to processing one by one
                    reprocess_serially(changes_chunk, processor)
                else:
                    # fall back to processing one by one for failed changes
                    for change, exception in change_exceptions:
                        handle_pillow_error(self, change, exception)
                    reprocess_serially(retry_changes, processor)
                processing_time += timer.duration
        # process on serial_processors
        for change in changes_chunk:
            processing_time += self.process_with_error_handling(change)
        self._record_datadog_metrics(changes_chunk, processing_time)

    def process_with_error_handling(self, change, processor=None):
        # process given change on all serial processors or given processor.
        # Tracks success/fail in datadog but not the timer metric, caller updates that
        timer = TimingContext()
        is_success = False
        try:
            with timer:
                if processor:
                    processor.process_change(change)
                else:
                    # process on serial processors
                    self.process_change(change, serial_only=True)
            is_success = True
        except Exception as ex:
            try:
                handle_pillow_error(self, change, ex)
            except Exception as e:
                notify_exception(None, 'processor error in pillow {} {}'.format(
                    self.get_name(), e,
                ))
                raise
        if is_success:
            self._record_change_success_in_datadog(change, processor)
        else:
            self._record_change_exception_in_datadog(change, processor)
        return timer.duration

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

    def _record_datadog_metrics(self, changes_chunk, processing_time):
        tags = ["pillow_name:{}".format(self.get_name()), "mode:chunked"]
        change_count = len(changes_chunk)
        if settings.ENTERPRISE_MODE:
            type_counter = Counter([
                change.metadata.document_subtype
                for change in changes_chunk if change.metadata.document_type == 'CommCareCase'
            ])
            for case_type, type_count in type_counter.items():
                tags_with_type = tags + ['case_type:{}'.format(case_type)]
                datadog_counter('commcare.change_feed.changes.count', type_count, tags=tags_with_type)

            remainder = change_count - sum(type_counter.values())
            if remainder:
                datadog_counter('commcare.change_feed.changes.count', remainder, tags=tags)
        else:
            datadog_counter('commcare.change_feed.changes.count', change_count, tags=tags)

        max_change_lag = (datetime.utcnow() - changes_chunk[0].metadata.publish_timestamp).total_seconds()
        min_change_lag = (datetime.utcnow() - changes_chunk[-1].metadata.publish_timestamp).total_seconds()
        datadog_gauge('commcare.change_feed.chunked.min_change_lag', min_change_lag, tags=tags)
        datadog_gauge('commcare.change_feed.chunked.max_change_lag', max_change_lag, tags=tags)

        # processing_time per change
        datadog_histogram(
            'commcare.change_feed.processing_time',
            processing_time / change_count,
            tags=tags + ["chunk_size:".format(str(change_count))]
        )

        if change_count == self.processor_chunk_size:
            # don't report offset chunks to ease up datadog calculations
            datadog_histogram('commcare.change_feed.chunked.processing_time_total', processing_time,
                              tags=tags + ["chunk_size:{}".format(str(change_count))])

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

    def _record_change_in_datadog(self, change, processing_time):
        self.__record_change_metric_in_datadog(
            'commcare.change_feed.changes.count', change,
            processing_time=processing_time, add_case_type_tag=True
        )

    def _record_batch_exception_in_datadog(self, processor):
        datadog_counter(
            "commcare.change_feed.batch_processor_exceptions",
            tags=[
                'pillow_name:{}'.format(self.get_name()),
                'processor:{}'.format(processor.__class__.__name__ if processor else "all_processors"),
            ])

    def _record_change_success_in_datadog(self, change, processor):
        self.__record_change_metric_in_datadog('commcare.change_feed.changes.success', change, processor)

    def _record_change_exception_in_datadog(self, change, processor):
        self.__record_change_metric_in_datadog('commcare.change_feed.changes.exceptions', change, processor)

    def __record_change_metric_in_datadog(self, metric, change, processor=None, processing_time=None,
                                          add_case_type_tag=False):
        if change.metadata is not None:
            common_tags = [
                'datasource:{}'.format(change.metadata.data_source_name),
                'is_deletion:{}'.format(change.metadata.is_deletion),
                'pillow_name:{}'.format(self.get_name()),
                'processor:{}'.format(processor.__class__.__name__ if processor else "all_processors"),
            ]

            metric_tags = list(common_tags)
            if add_case_type_tag and settings.ENTERPRISE_MODE and change.metadata.document_type == 'CommCareCase':
                metric_tags.append('case_type:{}'.format(change.metadata.document_subtype))

            datadog_counter(metric, tags=metric_tags)

            change_lag = (datetime.utcnow() - change.metadata.publish_timestamp).total_seconds()
            datadog_gauge('commcare.change_feed.change_lag', change_lag, tags=[
                'pillow_name:{}'.format(self.get_name()),
                _topic_for_ddog(change.topic),
            ])

            if processing_time:
                datadog_histogram('commcare.change_feed.processing_time', processing_time, tags=common_tags)

    @staticmethod
    def _deduplicate_changes(changes_chunk):
        seen = set()
        unique = []
        for change in reversed(changes_chunk):
            if change.id not in seen:
                unique.append(change)
                seen.add(change.id)
        unique.reverse()
        return unique


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
                 change_processed_event_handler=None, processor_chunk_size=0):
        self._name = name
        self._checkpoint = checkpoint
        self._change_feed = change_feed
        self.processor_chunk_size = processor_chunk_size
        if isinstance(processor, list):
            self.processors = processor
        else:
            self.processors = [processor]

        self._change_processed_event_handler = change_processed_event_handler

    @property
    def topics(self):
        return self._change_feed.topics

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

    def process_change(self, change, serial_only=False):
        processors = self.serial_processors if serial_only else self.processors
        for processor in processors:
            processor.process_change(change)

    def update_checkpoint(self, change, context):
        if self._change_processed_event_handler is not None:
            return self._change_processed_event_handler.update_checkpoint(change, context)
        return False


def handle_pillow_error(pillow, change, exception):
    from pillow_retry.models import PillowError

    pillow_logging.exception("[%s] Error on change: %s, %s" % (
        pillow.get_name(),
        change['id'],
        exception,
    ))

    datadog_counter('commcare.change_feed.changes.exceptions', tags=[
        'pillow_name:{}'.format(pillow.get_name()),
    ])

    # keep track of error attempt count
    change.increment_attempt_count()

    # always retry document missing errors, because the error is likely with couch
    if pillow.retry_errors or isinstance(exception, DocumentMissingError):
        error = PillowError.get_or_create(change, pillow)
        error.add_attempt(exception, sys.exc_info()[2], change.metadata)
        error.save()
