from abc import ABCMeta, abstractmethod

from corehq.util.es.elasticsearch import BulkIndexError, TransportError

from pillowtop.es_utils import (
    initialize_index_and_mapping,
    set_index_normal_settings,
    set_index_reindex_settings,
)
from pillowtop.feed.interface import Change
from pillowtop.logger import pillow_logging
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.utils import ErrorCollector, build_bulk_payload

from corehq.apps.change_feed.document_types import is_deletion
from corehq.util.argparse_types import date_type
from corehq.util.doc_processor.interface import (
    BaseDocProcessor,
    BulkDocProcessor,
)
from corehq.apps.es.client import manager

MAX_TRIES = 3
RETRY_TIME_DELAY_FACTOR = 15
MAX_PAYLOAD_SIZE = 10 ** 7  # ~10 MB


class Reindexer(metaclass=ABCMeta):
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


class ReindexerFactory(metaclass=ABCMeta):
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
            type=date_type,
            help='The start date (inclusive). format YYYY-MM-DD'
        )
        parser.add_argument(
            '--enddate',
            dest='end_date',
            type=date_type,
            help='The end date (exclusive). format YYYY-MM-DD'
        )


class PillowChangeProviderReindexer(Reindexer):
    start_from = None

    def __init__(self, pillow_or_processor, change_provider):
        self.pillow_or_processor = pillow_or_processor
        self.change_provider = change_provider

    def reindex(self):
        total_docs = 0
        for i, change in enumerate(self.change_provider.iter_all_changes()):
            try:
                # below works because signature is same for pillow and processor
                self.pillow_or_processor.process_change(change)
            except Exception:
                pillow_logging.exception("Unable to process change: %s", change.id)

            if i > 0 and i % 1000 == 0:
                pillow_logging.info("Processed %s docs", i)
            total_docs = i

        pillow_logging.info("Processed %s docs", total_docs)


def clean_index(index_name):
    if manager.index_exists(index_name):
        manager.index_delete(index=index_name)


def prepare_index_for_reindex(adapter):
    initialize_index_and_mapping(adapter)
    set_index_reindex_settings(adapter.index_name)


def prepare_index_for_usage(index_name):
    set_index_normal_settings(index_name)
    manager.index_refresh(index_name)


def _set_checkpoint(pillow):
    checkpoint_value = pillow.get_change_feed().get_latest_offsets_as_checkpoint_value()
    pillow_logging.info('setting checkpoint to {}'.format(checkpoint_value))
    pillow.checkpoint.update_to(checkpoint_value)


class ElasticPillowReindexer(PillowChangeProviderReindexer):
    in_place = False

    def __init__(
            self, pillow_or_processor, change_provider, adapter, in_place=False
    ):
        super(ElasticPillowReindexer, self).__init__(pillow_or_processor, change_provider)
        self.in_place = in_place
        self.adapter = adapter

    def clean(self):
        clean_index(self.adapter.index_name)

    def reindex(self):
        if not self.in_place and not self.start_from:
            prepare_index_for_reindex(self.adapter)
            if isinstance(self.pillow_or_processor, ConstructedPillow):
                _set_checkpoint(self.pillow_or_processor)

        super(ElasticPillowReindexer, self).reindex()

        prepare_index_for_usage(self.adapter.index_name)


class BulkPillowReindexProcessor(BaseDocProcessor):
    def __init__(self, adapter, doc_filter=None, process_deletes=False):
        self.doc_filter = doc_filter
        self.process_deletes = process_deletes
        self.adapter = adapter

    def should_process(self, doc):
        if self.doc_filter:
            return not self.doc_filter(doc)
        return True

    def process_bulk_docs(self, docs, progress_logger):
        if not docs:
            return True

        pillow_logging.info("Processing batch of %s docs", len(docs))
        changes = []
        for doc in docs:
            change = self._doc_to_change(doc)  # de-dupe the is_deletion check
            if self.process_deletes or not change.deleted:
                changes.append(change)
        error_collector = ErrorCollector()

        bulk_changes = build_bulk_payload(changes, error_collector)

        for change, exception in error_collector.errors:
            pillow_logging.error("Error processing doc %s: %s (%s)", change.id,
                                 type(exception), exception)

        try:
            self.adapter.bulk(bulk_changes)
        except BulkIndexError as e:
            pillow_logging.error("Bulk index errors\n%s", e.errors)
        except Exception as exc:
            pillow_logging.exception("Error sending bulk payload to Elasticsearch: %s", exc)
            return False

        return True

    @staticmethod
    def _doc_to_change(doc):
        return Change(id=doc['_id'], sequence_id=None, document=doc,
                      deleted=is_deletion(doc.get('doc_type')))


class ResumableBulkElasticPillowReindexer(Reindexer):
    reset = False
    in_place = False

    def __init__(self, doc_provider, adapter,
                 doc_filter=None, chunk_size=1000, pillow=None,
                 reset=False, in_place=False):
        self.reset = reset
        self.in_place = in_place
        self.doc_provider = doc_provider
        self.adapter = adapter
        self.chunk_size = chunk_size
        self.doc_processor = BulkPillowReindexProcessor(
            self.adapter, doc_filter, process_deletes=self.in_place
        )
        self.pillow = pillow

    def clean(self):
        clean_index(self.adapter.index_name)

    def reindex(self):
        if not manager.index_exists(self.adapter.index_name):
            self.reset = True  # if the index doesn't exist always reset the processing

        processor = BulkDocProcessor(
            self.doc_provider,
            self.doc_processor,
            reset=self.reset,
            chunk_size=self.chunk_size,
        )

        if not self.in_place and (self.reset or not processor.has_started()):
            prepare_index_for_reindex(self.adapter)
            if self.pillow:
                _set_checkpoint(self.pillow)

        processor.run()

        try:
            prepare_index_for_usage(self.adapter.index_name)
        except TransportError:
            raise Exception(
                'The Elasticsearch index was missing after reindex! If the index was manually deleted '
                'you can fix this by running ./manage.py ptop_reindexer_v2 [index-name] --reset or '
                './manage.py ptop_preindex --reset.'
            )
