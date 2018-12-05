from __future__ import absolute_import
from __future__ import unicode_literals

from abc import ABCMeta, abstractmethod
import argparse
from datetime import datetime
import time

from elasticsearch import TransportError
import six

from corehq.apps.change_feed.document_types import is_deletion
from corehq.util.doc_processor.interface import BaseDocProcessor, BulkDocProcessor
from pillowtop.es_utils import set_index_reindex_settings, \
    set_index_normal_settings, initialize_mapping_if_necessary
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.logger import pillow_logging
from pillowtop.utils import prepare_bulk_payloads, build_bulk_payload, ErrorCollector

MAX_TRIES = 3
RETRY_TIME_DELAY_FACTOR = 15
MAX_PAYLOAD_SIZE = 10 ** 7  # ~10 MB
DATE_FORMAT = "%Y-%m-%d"


def valid_date(s):
    try:
        return datetime.strptime(s, DATE_FORMAT)
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


class Reindexer(six.with_metaclass(ABCMeta)):
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


class ReindexerFactory(six.with_metaclass(ABCMeta)):
    slug = None
    arg_contributors = None

    def __init__(self, **options):
        self.options = options

    @classmethod
    def add_arguments(cls, parser):
        if not cls.arg_contributors:
            return

        for contributor in cls.arg_contributors:
            contributor(parser)

    @abstractmethod
    def build(self):
        """
        :param options: dict of options
        :return: a fully configured reindexer
        """
        raise NotImplementedError

    @staticmethod
    def elastic_reindexer_args(parser):
        parser.add_argument(
            '--in-place',
            action='store_true',
            dest='in_place',
            help='Run the reindex in place - assuming it is against a live index.'
        )

    @staticmethod
    def resumable_reindexer_args(parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            dest='reset',
            help='Reset a resumable reindex'
        )
        parser.add_argument(
            '--chunksize',
            type=int,
            action='store',
            dest='chunk_size',
            default=1000,
            help='Number of docs to process at a time'
        )

    @staticmethod
    def limit_db_args(parser):
        parser.add_argument(
            '--limit-to-db',
            dest='limit_to_db',
            help="Limit the reindexer to only a specific SQL database. Allows running multiple in parallel."
        )

    @staticmethod
    def domain_arg(parser):
        parser.add_argument(
            '--domain',
            dest='domain',
        )

    @staticmethod
    def server_modified_on_arg(parser):
        parser.add_argument(
            '--startdate',
            dest='start_date',
            type=valid_date,
            help='The start date (inclusive). format YYYY-MM-DD'
        )
        parser.add_argument(
            '--enddate',
            dest='end_date',
            type=valid_date,
            help='The end date (exclusive). format YYYY-MM-DD'
        )


class PillowChangeProviderReindexer(Reindexer):
    start_from = None

    def __init__(self, pillow_or_processor, change_provider):
        self.pillow_or_processor = pillow_or_processor
        self.change_provider = change_provider

    def reindex(self):
        for i, change in enumerate(self.change_provider.iter_all_changes()):
            try:
                # below works because signature is same for pillow and processor
                self.pillow_or_processor.process_change(change)
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

    def __init__(self, pillow_or_processor, change_provider, elasticsearch, index_info, in_place=False):
        super(ElasticPillowReindexer, self).__init__(pillow_or_processor, change_provider)
        self.es = elasticsearch
        self.index_info = index_info
        self.in_place = in_place

    def clean(self):
        _clean_index(self.es, self.index_info)

    def reindex(self):
        if not self.in_place and not self.start_from:
            _prepare_index_for_reindex(self.es, self.index_info)
            if isinstance(self.pillow_or_processor, ConstructedPillow):
                _set_checkpoint(self.pillow_or_processor)

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
            pillow_logging.error("Error procesing doc %s: %s (%s)", change.id, type(exception), exception)

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
                self.es.bulk(payload.decode('utf-8'))
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
                 doc_filter=None, doc_transform=None, chunk_size=1000, pillow=None,
                 reset=False, in_place=False):
        self.reset = reset
        self.in_place = in_place
        self.doc_provider = doc_provider
        self.es = elasticsearch
        self.index_info = index_info
        self.chunk_size = chunk_size
        self.doc_processor = BulkPillowReindexProcessor(
            self.es, self.index_info, doc_filter, doc_transform
        )
        self.pillow = pillow

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
