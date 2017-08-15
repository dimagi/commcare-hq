import time
from abc import ABCMeta, abstractmethod
from datetime import datetime
from elasticsearch import TransportError

import six
from corehq.apps.change_feed.document_types import is_deletion
from corehq.util.doc_processor.interface import BaseDocProcessor, BulkDocProcessor
from pillowtop.es_utils import set_index_reindex_settings, \
    set_index_normal_settings, initialize_mapping_if_necessary
from pillowtop.feed.interface import Change
from pillowtop.logger import pillow_logging
from pillowtop.utils import prepare_bulk_payloads, build_bulk_payload, ErrorCollector

MAX_TRIES = 3
RETRY_TIME_DELAY_FACTOR = 15
MAX_PAYLOAD_SIZE = 10 ** 7  # ~10 MB


class Reindexer(six.with_metaclass(ABCMeta)):
    def consume_options(self, options):
        """Called from the management command with the command line
        options.

        :param options: command line options dict
        :return: dict of unprocessed options
        """
        return options

    def clean(self):
        """
            Cleans the index.

            This can be called prior to reindex to ensure starting from a clean slate.
            Should be overridden on a case-by-case basis by subclasses.
            """
        pass

    @abstractmethod
    def reindex(self):
        """Perform the reindex"""
        raise NotImplementedError


class UnexpectedOptionException(Exception):
    def __init__(self, reindexer_slug, extras):
        super(UnexpectedOptionException, self).__init__(
            "The following options don't apply "
            "to the reindexer ({}): {}".format(reindexer_slug, ','.join(list(extras)))
        )


class ReindexerFactory(six.with_metaclass(ABCMeta)):
    valid_options = None
    slug = None

    def __init__(self, **options):
        self.validate_options(options)
        self.options = options

    def validate_options(self, options):
        extras = set(options) - set(self.valid_options or [])
        if extras:
            raise UnexpectedOptionException(self.slug, extras)

    @abstractmethod
    def build(self):
        """
        :param options: dict of options
        :return: a fully configured reindexer
        """
        raise NotImplementedError


class PillowReindexer(Reindexer):
    def __init__(self, pillow):
        self.pillow = pillow


class PillowChangeProviderReindexer(PillowReindexer):
    start_from = None

    def __init__(self, pillow, change_provider):
        super(PillowChangeProviderReindexer, self).__init__(pillow)
        self.change_provider = change_provider

    def consume_options(self, options):
        return options

    def reindex(self):
        for i, change in enumerate(self.change_provider.iter_all_changes()):
            try:
                self.pillow.process_change(change)
            except Exception:
                pillow_logging.exception("Unable to process change: %s", change.id)

            if i % 1000:
                pillow_logging.info("Processed %s docs", i)


def _clean_index(es, index_info):
    if es.indices.exists(index_info.index):
        es.indices.delete(index=index_info.index)


def _prepare_index_for_reindex(es, index_info):
    if not es.indices.exists(index_info.index):
        es.indices.create(index=index_info.index, body=index_info.meta)
    initialize_mapping_if_necessary(es, index_info)
    set_index_reindex_settings(es, index_info.index)


def _prepare_index_for_usage(es, index_info):
    set_index_normal_settings(es, index_info.index)
    es.indices.refresh(index_info.index)


def _set_checkpoint(pillow):
    checkpoint_value = pillow.get_change_feed().get_latest_offsets_as_checkpoint_value()
    pillow_logging.info('setting checkpoint to {}'.format(checkpoint_value))
    pillow.checkpoint.update_to(checkpoint_value)


class ElasticPillowReindexer(PillowChangeProviderReindexer):
    in_place = False

    def __init__(self, pillow, change_provider, elasticsearch, index_info):
        super(ElasticPillowReindexer, self).__init__(pillow, change_provider)
        self.es = elasticsearch
        self.index_info = index_info

    def consume_options(self, options):
        super(ElasticPillowReindexer, self).consume_options(options)
        self.in_place = options.pop("in-place", False)

    def clean(self):
        _clean_index(self.es, self.index_info)

    def reindex(self):
        if not self.in_place and not self.start_from:
            _prepare_index_for_reindex(self.es, self.index_info)
            _set_checkpoint(self.pillow)

        super(ElasticPillowReindexer, self).reindex()

        _prepare_index_for_usage(self.es, self.index_info)


class BulkPillowReindexProcessor(BaseDocProcessor):
    def __init__(self, es_client, index_info, doc_filter=None, doc_transform=None):
        self.doc_transform = doc_transform
        self.doc_filter = doc_filter
        self.es = es_client
        self.index_info = index_info

    def should_process(self, doc):
        if self.doc_filter:
            return not self.doc_filter(doc)
        return True

    def process_bulk_docs(self, docs):
        if len(docs) == 0:
            return True

        pillow_logging.info("Processing batch of %s docs", len((docs)))

        changes = [self._doc_to_change(doc) for doc in docs]
        error_collector = ErrorCollector()

        bulk_changes = build_bulk_payload(self.index_info, changes, self.doc_transform, error_collector)

        for change, exception in error_collector.errors:
            pillow_logging.error("Error procesing doc %s: %s", change.id, exception)

        payloads = prepare_bulk_payloads(bulk_changes, MAX_PAYLOAD_SIZE)
        if len(payloads) > 1:
            pillow_logging.info("Payload split into %s parts" % len(payloads))

        for payload in payloads:
            success = self._send_payload_with_retries(payload)
            if not success:
                # stop the reindexer if we're unable to send a payload to ES
                return False

        return True

    def _send_payload_with_retries(self, payload):
        pillow_logging.info("Sending payload to ES")

        retries = 0
        bulk_start = datetime.utcnow()
        success = False
        while retries < MAX_TRIES:
            if retries:
                retry_time = (datetime.utcnow() - bulk_start).seconds + retries * RETRY_TIME_DELAY_FACTOR
                pillow_logging.warning("\tRetrying in %s seconds" % retry_time)
                time.sleep(retry_time)
                pillow_logging.warning("\tRetrying now ...")
                # reset timestamp when looping again
                bulk_start = datetime.utcnow()

            try:
                self.es.bulk(payload)
                success = True
                break
            except Exception:
                retries += 1
                pillow_logging.exception("\tException sending payload to ES")

        return success

    @staticmethod
    def _doc_to_change(doc):
        return Change(
            id=doc['_id'], sequence_id=None, document=doc, deleted=is_deletion(doc.get('doc_type'))
        )


class ResumableBulkElasticPillowReindexer(Reindexer):
    reset = False
    in_place = False

    def __init__(self, doc_provider, elasticsearch, index_info,
                 doc_filter=None, doc_transform=None, chunk_size=1000, pillow=None):
        self.doc_provider = doc_provider
        self.es = elasticsearch
        self.index_info = index_info
        self.chunk_size = chunk_size
        self.doc_processor = BulkPillowReindexProcessor(
            self.es, self.index_info, doc_filter, doc_transform
        )
        self.pillow = pillow

    def consume_options(self, options):
        self.reset = options.pop("reset", False)
        self.in_place = options.pop("in-place", False)
        chunk_size = options.pop("chunksize", None)
        if chunk_size:
            self.chunk_size = chunk_size
        return options

    def clean(self):
        _clean_index(self.es, self.index_info)

    def reindex(self):
        if not self.es.indices.exists(self.index_info.index):
            self.reset = True  # if the index doesn't exist always reset the processing

        processor = BulkDocProcessor(
            self.doc_provider,
            self.doc_processor,
            reset=self.reset,
            chunk_size=self.chunk_size,
        )

        if not self.in_place and (self.reset or not processor.has_started()):
            _prepare_index_for_reindex(self.es, self.index_info)
            if self.pillow:
                _set_checkpoint(self.pillow)

        processor.run()

        try:
            _prepare_index_for_usage(self.es, self.index_info)
        except TransportError:
            raise Exception(
                'The Elasticsearch index was missing after reindex! If the index was manually deleted '
                'you can fix this by running ./manage.py ptop_reindexer_v2 [index-name] --reset or '
                './manage.py ptop_preindex --reset.'
            )
